"""Patchbay metadata refresh — sync, sweep, resurrect."""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

from calmlib.utils.patchbay.core.db import (
    _doc_to_session,
    _find_claude_conversation_jsonl,
    _find_session_doc,
    get_collection,
    get_empty_collection,
)
from calmlib.utils.patchbay.core.models import SessionInfo, Topics

AI_MODEL_PREFIXES = ("claude-sonnet", "claude-haiku")

EXIT_PHRASES = frozenset([
    "goodbye!", "see ya!", "catch you later!", "bye!", "later!",
    "take care!", "cheers!", "peace!", "adios!", "ciao!",
])
CODEX_SESSIONS_DIR = Path.home() / ".codex" / "sessions"
CODEX_ARCHIVED_SESSIONS_DIR = Path.home() / ".codex" / "archived_sessions"
CODEX_SESSION_INDEX = Path.home() / ".codex" / "session_index.jsonl"


def _extract_claude_name_fields(jsonl_path: Path) -> dict[str, str | None]:
    """Extract Claude-native title fields from a session JSONL file."""
    custom_title = None
    agent_name = None

    try:
        for line in jsonl_path.open():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type")
            if entry_type == "custom-title":
                value = entry.get("customTitle")
                if isinstance(value, str) and value.strip():
                    custom_title = value.strip()
            elif entry_type == "agent-name":
                value = entry.get("agentName")
                if isinstance(value, str) and value.strip():
                    agent_name = value.strip()
    except OSError:
        return {
            "claude_custom_title": None,
            "claude_agent_name": None,
            "title": None,
            "title_source": None,
        }

    preferred_title = custom_title or agent_name
    title_source = None
    if custom_title:
        title_source = "claude_custom_title"
    elif agent_name:
        title_source = "claude_agent_name"

    return {
        "claude_custom_title": custom_title,
        "claude_agent_name": agent_name,
        "title": preferred_title,
        "title_source": title_source,
    }


def _extract_session_model(jsonl_path: Path) -> str | None:
    """Extract the model name from the first assistant message in a JSONL file."""
    try:
        for line in jsonl_path.open():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "assistant":
                return entry.get("message", {}).get("model")
    except (PermissionError, OSError):
        pass
    return None


def _find_codex_conversation_jsonl(session_id: str) -> Path | None:
    """Find the Codex JSONL file for a session, including archived sessions."""
    if CODEX_SESSIONS_DIR.exists():
        matches = sorted(CODEX_SESSIONS_DIR.glob(f"**/*{session_id}.jsonl"))
        if matches:
            return matches[-1]
    if CODEX_ARCHIVED_SESSIONS_DIR.exists():
        matches = sorted(CODEX_ARCHIVED_SESSIONS_DIR.glob(f"*{session_id}.jsonl"))
        if matches:
            return matches[-1]
    return None


def _get_codex_thread_name(session_id: str) -> str | None:
    if not CODEX_SESSION_INDEX.exists():
        return None

    try:
        for line in CODEX_SESSION_INDEX.open():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("id") != session_id:
                continue
            thread_name = entry.get("thread_name")
            if isinstance(thread_name, str) and thread_name.strip():
                return thread_name.strip()
    except OSError:
        return None

    return None


def _extract_codex_session_meta(jsonl_path: Path) -> dict[str, str | None]:
    """Extract id/cwd/timestamp from Codex session JSONL."""
    try:
        for line in jsonl_path.open():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "session_meta":
                continue

            payload = entry.get("payload", {})
            timestamp = payload.get("timestamp")
            if isinstance(timestamp, str) and timestamp.endswith("Z"):
                timestamp = timestamp.replace("Z", "+00:00")

            return {
                "session_id": payload.get("id"),
                "cwd": payload.get("cwd"),
                "timestamp": timestamp,
            }
    except OSError:
        return {
            "session_id": None,
            "cwd": None,
            "timestamp": None,
        }

    return {
        "session_id": None,
        "cwd": None,
        "timestamp": None,
    }


def get_claude_name_fields(session_id: str) -> dict[str, str | None]:
    """Load Claude-native title fields for a session, if available."""
    jsonl_path = _find_claude_conversation_jsonl(session_id)
    if not jsonl_path:
        return {
            "claude_custom_title": None,
            "claude_agent_name": None,
            "title": None,
            "title_source": None,
        }
    return _extract_claude_name_fields(jsonl_path)


def _normalize_session_title(title: str) -> str:
    stripped = title.strip()
    if not stripped:
        raise ValueError("Session title must be non-empty")
    return stripped


_NOISE_TAG_PATTERNS = [
    re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL),
    re.compile(r"<command-name>.*?</command-name>", re.DOTALL),
    re.compile(r"<command-message>.*?</command-message>", re.DOTALL),
    re.compile(r"<command-args>.*?</command-args>", re.DOTALL),
    re.compile(r"<local-command-stdout>.*?</local-command-stdout>", re.DOTALL),
    re.compile(r"<local-command-stderr>.*?</local-command-stderr>", re.DOTALL),
    re.compile(r"<bash-input>.*?</bash-input>", re.DOTALL),
    re.compile(r"<bash-stdout>.*?</bash-stdout>", re.DOTALL),
    re.compile(r"<bash-stderr>.*?</bash-stderr>", re.DOTALL),
]


def _strip_noise_tags(text: str) -> str:
    for pat in _NOISE_TAG_PATTERNS:
        text = pat.sub("", text)
    return text.strip()


_SKILL_LOAD_PREFIXES = (
    "Base directory for this skill:",
    "Skill directory:",
)


def _iter_real_user_message_texts(jsonl_path: Path):
    """Yield real human user message texts from a JSONL file (excludes exit/system noise)."""
    try:
        for line in jsonl_path.open():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "user":
                continue
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                # Concatenate ALL text blocks; skip tool_result/tool_use blocks.
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                text = "\n".join(parts)
            else:
                continue

            cleaned = _strip_noise_tags(text)
            if len(cleaned) < 5:
                continue
            # Skill-load preambles
            if cleaned.startswith(_SKILL_LOAD_PREFIXES):
                continue
            # Pure tag wrapper with nothing meaningful inside
            if cleaned.startswith("<") and cleaned.endswith(">"):
                inner = re.sub(r"<[^>]+>", "", cleaned).strip().lower()
                if not inner or inner in EXIT_PHRASES or len(inner) < 5:
                    continue
            yield cleaned
    except (PermissionError, OSError):
        return


def _count_real_user_messages(jsonl_path: Path) -> int:
    """Count real human user messages in a JSONL file (excludes exit/system noise)."""
    try:
        return sum(1 for _ in _iter_real_user_message_texts(jsonl_path))
    except (PermissionError, OSError):
        return -1


def _collect_real_user_messages(jsonl_path: Path, limit: int = 12) -> list[str]:
    """Collect first `limit` real human user message texts from a JSONL file."""
    out: list[str] = []
    for text in _iter_real_user_message_texts(jsonl_path):
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _first_and_last_real_user_messages(jsonl_path: Path) -> tuple[str | None, str | None]:
    """Return (first, last) real user message texts from a JSONL file."""
    first: str | None = None
    last: str | None = None
    for text in _iter_real_user_message_texts(jsonl_path):
        if first is None:
            first = text
        last = text
    return first, last


_WRAPUP_PATTERN = re.compile(
    r"<command-name>\s*/?session-wrapup\s*</command-name>", re.IGNORECASE
)


def _scan_wrapup_invoked(jsonl_path: Path) -> bool:
    """Scan all user messages for /session-wrapup invocation."""
    try:
        for line in jsonl_path.open():
            if "session-wrapup" not in line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") != "user":
                continue
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                parts = [b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text"]
                text = "\n".join(parts)
            else:
                continue
            if _WRAPUP_PATTERN.search(text):
                return True
    except (PermissionError, OSError):
        return False
    return False


def _get_jsonl_mtime(session_id: str) -> float | None:
    """Get mtime of a session's JSONL file, or None if not found."""
    jsonl_path = _find_claude_conversation_jsonl(session_id)
    if not jsonl_path:
        return None
    try:
        return jsonl_path.stat().st_mtime
    except OSError:
        return None


def generate_topics(session_id: str, force: bool = False) -> str | None:
    """Generate topics_short for a session from its first messages via LLM."""
    col = get_collection()
    doc = _find_session_doc(col, session_id)
    if not doc:
        return None

    full_id = doc["session_id"]

    if not force and doc.get("topic_keywords"):
        return ", ".join(doc["topic_keywords"])
    if not force and doc.get("topics_short"):
        return doc["topics_short"]

    user_texts = _user_messages_for_metadata(full_id, doc.get("cwd"))
    if not user_texts:
        return None

    try:
        from calmlib.llm import query_llm_structured

        context = "\n---\n".join(t[:300] for t in user_texts[:8])
        title = doc.get("title") or "(untitled)"
        prompt = (
            f"Session title: {title}\n\n"
            f"User messages:\n{context}\n\n"
            "Extract 2-4 short keyword topics that describe what this coding session is about. "
            "Each keyword should be 1-2 words. Focus on the technical domain, not generic words."
        )

        result = query_llm_structured(prompt, output_schema=Topics, model="claude-4.5-haiku")
        keywords = [k.strip() for k in result.keywords if k and k.strip()]
        topics_str = ", ".join(keywords)

        col.update_one(
            {"session_id": full_id},
            {"$set": {"topic_keywords": keywords, "topics_short": topics_str}},
        )
        logger.info(f"Generated topics for {full_id[:12]}: {topics_str}")
        return topics_str

    except Exception as exc:
        logger.warning(f"Failed to generate topics for {full_id[:12]}: {exc}")
        return None


def _user_messages_for_metadata(
    session_id: str, cwd: str | None, limit: int = 12
) -> list[str]:
    """Get real user messages for metadata generation. Prefers JSONL (cheap), falls back to SDK."""
    jsonl_path = _find_claude_conversation_jsonl(session_id)
    if jsonl_path:
        msgs = _collect_real_user_messages(jsonl_path, limit=limit)
        if msgs:
            return msgs

    try:
        from calmlib.utils.patchbay.digest import (
            _extract_text_from_content,
            _is_real_human_message,
            get_session_messages_raw,
        )
    except ImportError:
        return []

    raw_messages = get_session_messages_raw(session_id, cwd=cwd)
    if not raw_messages:
        return []

    out: list[str] = []
    for msg in raw_messages:
        if msg.get("type") != "user":
            continue
        message_data = msg.get("message", msg)
        text = _extract_text_from_content(message_data.get("content", ""))
        if _is_real_human_message(text):
            out.append(text)
            if len(out) >= limit:
                break
    return out


def _build_title_description(doc: dict, user_messages: list[str] | None = None) -> str | None:
    """Build a rich description for title generation from all available session context.

    `user_messages` should be the real human messages from the session — these become
    the primary input to the title model. Topics, project, and Claude's own title
    are auxiliary hints only.
    """
    parts = []

    if user_messages:
        msg_block = "\n---\n".join(m[:400] for m in user_messages[:8])
        parts.append(f"User messages:\n{msg_block}")
    elif doc.get("first_message"):
        fm = doc["first_message"].strip()
        if not fm.startswith("<"):
            parts.append(f"User request: {fm[:400]}")

    if doc.get("claude_custom_title"):
        parts.append(f"Claude's title: {doc['claude_custom_title']}")

    keywords = doc.get("topic_keywords")
    if keywords:
        parts.append(f"Topics: {', '.join(keywords)}")
    elif doc.get("topics_short"):
        parts.append(f"Topics: {doc['topics_short']}")

    if doc.get("task_description"):
        parts.append(f"Task: {doc['task_description'][:200]}")

    if doc.get("project"):
        parts.append(f"Project: {doc['project']}")

    if not parts:
        return None

    return "\n\n".join(parts)


def refresh_session_metadata(session_id: str, force: bool = False) -> SessionInfo | None:
    """Refresh a single session's metadata from client-native sources."""
    col = get_collection()
    doc = _find_session_doc(col, session_id)
    if not doc:
        return None

    client = doc.get("client", "claude")
    if client == "codex":
        full_session_id = doc["session_id"]
        update: dict = {}

        thread_name = _get_codex_thread_name(full_session_id)
        if thread_name and (
            thread_name != doc.get("title")
            or doc.get("title_source") != "codex_thread_name"
        ):
            update["title"] = thread_name
            update["title_source"] = "codex_thread_name"

        jsonl_path = _find_codex_conversation_jsonl(full_session_id)
        if jsonl_path:
            meta = _extract_codex_session_meta(jsonl_path)
            cwd = meta.get("cwd")
            if cwd and cwd != doc.get("cwd"):
                update["cwd"] = cwd

            started_at = meta.get("timestamp")
            if started_at:
                try:
                    parsed_timestamp = datetime.fromisoformat(started_at)
                except ValueError:
                    parsed_timestamp = None
                if parsed_timestamp and parsed_timestamp != doc.get("timestamp"):
                    update["timestamp"] = parsed_timestamp

        if doc.get("message_count") is None:
            update["message_count"] = -1

        if update:
            col.update_one({"session_id": full_session_id}, {"$set": update})
            doc.update(update)
            logger.info(f"Refreshed {full_session_id[:12]} from Codex session metadata")

        return _doc_to_session(doc)

    if client != "claude":
        return _doc_to_session(doc)

    full_session_id = doc["session_id"]
    jsonl_path = _find_claude_conversation_jsonl(full_session_id)

    current_mtime = None
    jsonl_changed = force
    if jsonl_path:
        try:
            current_mtime = jsonl_path.stat().st_mtime
        except OSError:
            pass
        stored_mtime = doc.get("jsonl_mtime")
        if stored_mtime is None or (current_mtime and current_mtime > stored_mtime):
            jsonl_changed = True

    title_fields = get_claude_name_fields(full_session_id)
    update: dict = {}

    custom_title = title_fields.get("claude_custom_title")
    if custom_title and custom_title != doc.get("claude_custom_title"):
        update["claude_custom_title"] = custom_title

    agent_name = title_fields.get("claude_agent_name")
    if agent_name and agent_name != doc.get("claude_agent_name"):
        update["claude_agent_name"] = agent_name

    if jsonl_path and (doc.get("message_count") is None or jsonl_changed):
        real_msgs = _count_real_user_messages(jsonl_path)
        if real_msgs >= 0 and real_msgs != doc.get("message_count"):
            update["message_count"] = real_msgs
            if doc.get("message_count") is None:
                logger.warning(f"Fixed missing message_count for {full_session_id[:12]}: {real_msgs}")

    if jsonl_path and (jsonl_changed or not doc.get("first_message") or not doc.get("last_message")):
        first, last = _first_and_last_real_user_messages(jsonl_path)
        if first and first != doc.get("first_message"):
            update["first_message"] = first
        if last and last != doc.get("last_message"):
            update["last_message"] = last

    if jsonl_path and (jsonl_changed or doc.get("wrapup_invoked") is None):
        invoked = _scan_wrapup_invoked(jsonl_path)
        if invoked != doc.get("wrapup_invoked"):
            update["wrapup_invoked"] = invoked

    if jsonl_path and not doc.get("model"):
        model = _extract_session_model(jsonl_path)
        if model:
            update["model"] = model
            if any(model.startswith(prefix) for prefix in AI_MODEL_PREFIXES):
                if doc.get("source") != "ai":
                    update["source"] = "ai"
                    logger.info(f"Corrected source to 'ai' for {full_session_id[:12]} (model={model})")

    if current_mtime and current_mtime != doc.get("jsonl_mtime"):
        update["jsonl_mtime"] = current_mtime

    if current_mtime:
        last_activity = datetime.fromtimestamp(current_mtime, tz=timezone.utc).replace(tzinfo=None)
        if last_activity != doc.get("last_activity_at"):
            update["last_activity_at"] = last_activity
    elif doc.get("last_activity_at") is None and doc.get("timestamp"):
        update["last_activity_at"] = doc["timestamp"]

    if update:
        col.update_one({"session_id": full_session_id}, {"$set": update})
        doc.update(update)
        logger.info(f"Refreshed {full_session_id[:12]} from Claude JSONL")

    if jsonl_changed or not doc.get("topic_keywords"):
        topics = generate_topics(full_session_id, force=jsonl_changed)
        if topics:
            doc["topics_short"] = topics
            doc["topic_keywords"] = [k.strip() for k in topics.split(",") if k.strip()]

    if jsonl_changed or not doc.get("title") or doc.get("title_source") not in ("manual", "styled"):
        if doc.get("title_source") != "manual":
            user_messages = _user_messages_for_metadata(full_session_id, doc.get("cwd"))
            description = _build_title_description(doc, user_messages=user_messages)
            if description:
                try:
                    from calmlib.utils.patchbay.title_style import generate_styled_title

                    styled = generate_styled_title(description, seed=full_session_id)
                    if styled:
                        title_update = {
                            "title": styled,
                            "title_source": "styled",
                        }
                        col.update_one({"session_id": full_session_id}, {"$set": title_update})
                        doc.update(title_update)
                        logger.info(f"Styled title for {full_session_id[:12]}: {styled}")
                    else:
                        logger.warning(
                            f"Styled title for {full_session_id[:12]} came back empty — leaving title unset"
                        )
                except Exception as exc:
                    logger.warning(f"Failed to generate styled title for {full_session_id[:12]}: {exc}")

    col.update_one(
        {"session_id": full_session_id},
        {"$set": {"metadata_refreshed_at": datetime.now()}},
    )

    return _doc_to_session(doc)


def bulk_refresh_metadata(
    limit: int | None = None,
    since_hours: int | None = None,
    human_only: bool = False,
) -> list[SessionInfo]:
    """Bulk-refresh metadata. Skips sessions whose JSONL mtime is unchanged.

    With defaults (limit=None, since_hours=None), scans every non-dismissed session
    and only touches those with newer JSONL mtime or missing last_activity_at.
    """
    col = get_collection()
    filter_doc: dict = {"status": {"$nin": ["dismissed"]}}
    if since_hours is not None:
        filter_doc["timestamp"] = {"$gte": datetime.now() - timedelta(hours=since_hours)}
    if human_only:
        filter_doc["source"] = "human"

    cursor = col.find(filter_doc).sort("timestamp", -1)
    if limit is not None:
        cursor = cursor.limit(limit)

    updated: list[SessionInfo] = []
    for doc in cursor:
        sid = doc["session_id"]
        client = doc.get("client", "claude")

        if client == "claude":
            jsonl_path = _find_claude_conversation_jsonl(sid)
            if jsonl_path:
                try:
                    current_mtime = jsonl_path.stat().st_mtime
                except OSError:
                    current_mtime = None
                stored_mtime = doc.get("jsonl_mtime")
                mtime_unchanged = (
                    stored_mtime is not None
                    and current_mtime is not None
                    and current_mtime <= stored_mtime
                )
                metadata_complete = (
                    doc.get("last_activity_at") is not None
                    and doc.get("first_message")
                    and doc.get("topic_keywords")
                    and doc.get("wrapup_invoked") is not None
                )
                if mtime_unchanged and metadata_complete:
                    continue

        try:
            result = refresh_session_metadata(sid)
            if result:
                updated.append(result)
        except Exception as exc:
            logger.warning(f"Failed to refresh {sid[:12]}: {exc}")
    return updated


def cleanup_empty_sessions(max_age_hours: int = 1, dry_run: bool = True) -> int:
    """Mark empty sessions older than max_age_hours as 'dismissed'."""
    col = get_collection()

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    filter_doc = {
        "status": "empty",
        "timestamp": {"$lt": cutoff},
    }

    if dry_run:
        count = col.count_documents(filter_doc)
        logger.info(f"[dry_run] Would dismiss {count} empty sessions older than {max_age_hours}h")
        return count

    result = col.update_many(filter_doc, {"$set": {"status": "dismissed"}})
    logger.info(f"Dismissed {result.modified_count} empty sessions older than {max_age_hours}h")
    return result.modified_count


def sweep_empty_sessions(max_age_hours: int = 1, dry_run: bool = True) -> int:
    """Move sessions with 0 real user messages to the empty_sessions collection."""
    col = get_collection()
    empty_col = get_empty_collection()

    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    candidates = col.find({
        "timestamp": {"$lt": cutoff},
        "status": {"$nin": ["archived", "dismissed"]},
    })

    moved = 0
    for doc in candidates:
        sid = doc["session_id"]

        if empty_col.find_one({"session_id": sid}):
            continue

        jsonl_path = _find_claude_conversation_jsonl(sid)
        if not jsonl_path:
            real_msgs = 0
            mtime = None
        else:
            real_msgs = _count_real_user_messages(jsonl_path)
            if real_msgs < 0:
                continue
            try:
                mtime = jsonl_path.stat().st_mtime
            except OSError:
                mtime = None

        if real_msgs > 0:
            continue

        if dry_run:
            title = doc.get("title", "(none)")
            logger.info(f"[dry_run] Would park {sid[:12]} ({title})")
            moved += 1
            continue

        doc.pop("_id", None)
        doc["parked_at"] = datetime.now()
        doc["jsonl_mtime"] = mtime
        empty_col.update_one({"session_id": sid}, {"$set": doc}, upsert=True)
        col.delete_one({"session_id": sid})
        logger.info(f"Parked {sid[:12]} → empty_sessions")
        moved += 1

    logger.info(f"Sweep complete: {moved} sessions {'would be' if dry_run else ''} parked")
    return moved


def resurrect_sessions() -> int:
    """Check empty_sessions for JSONL mtime changes; resurrect if new content."""
    empty_col = get_empty_collection()
    col = get_collection()

    resurrected = 0
    for doc in empty_col.find():
        sid = doc["session_id"]
        stored_mtime = doc.get("jsonl_mtime")

        current_mtime = _get_jsonl_mtime(sid)
        if current_mtime is None:
            continue

        if stored_mtime is not None and current_mtime <= stored_mtime:
            continue

        jsonl_path = _find_claude_conversation_jsonl(sid)
        if not jsonl_path:
            continue
        real_msgs = _count_real_user_messages(jsonl_path)
        if real_msgs <= 0:
            empty_col.update_one(
                {"session_id": sid},
                {"$set": {"jsonl_mtime": current_mtime}},
            )
            continue

        doc.pop("_id", None)
        doc.pop("parked_at", None)
        doc.pop("jsonl_mtime", None)
        col.update_one({"session_id": sid}, {"$set": doc}, upsert=True)
        empty_col.delete_one({"session_id": sid})
        logger.info(f"Resurrected {sid[:12]} → agent_sessions ({real_msgs} real msgs)")
        resurrected += 1

    logger.info(f"Resurrect check complete: {resurrected} sessions restored")
    return resurrected
