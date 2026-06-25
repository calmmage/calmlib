"""Patchbay search & session ops — list, search, count, link, tag, launch."""

from datetime import datetime, timedelta

from claude_agent_sdk import rename_session as claude_rename_session
from loguru import logger

from calmlib.utils.patchbay.core.db import (
    _doc_to_session,
    _find_session_doc,
    get_collection,
)
from calmlib.utils.patchbay.core.models import SessionInfo
from calmlib.utils.patchbay.core.refresh import (
    _normalize_session_title,
    refresh_session_metadata,
)


def search_sessions(
    query: str,
    human_only: bool = True,
    limit: int = 10,
    exclude_empty: bool = True,
    exclude_archived: bool = True,
    exclude_done: bool = True,
) -> list[SessionInfo]:
    """Search sessions by regex across title, topics, and first_message."""
    col = get_collection()

    filter_doc: dict = {
        "$or": [
            {"title": {"$regex": query, "$options": "i"}},
            {"claude_custom_title": {"$regex": query, "$options": "i"}},
            {"claude_agent_name": {"$regex": query, "$options": "i"}},
            {"topics_short": {"$regex": query, "$options": "i"}},
            {"first_message": {"$regex": query, "$options": "i"}},
        ]
    }
    if human_only:
        filter_doc["source"] = "human"

    exclude_statuses = ["dismissed"]
    if exclude_empty:
        exclude_statuses.append("empty")
    if exclude_archived:
        exclude_statuses.append("archived")
    if exclude_done:
        exclude_statuses.append("done")
    filter_doc["status"] = {"$nin": exclude_statuses}

    docs = col.find(filter_doc).sort("timestamp", -1).limit(limit)
    return [_doc_to_session(doc) for doc in docs]


def list_sessions(
    human_only: bool = True,
    limit: int = 20,
    since: datetime | None = None,
    status: str | None = None,
    client: str | None = None,
) -> list[SessionInfo]:
    """List recent sessions with filters. Sorted by last_activity_at (falling back to timestamp)."""
    col = get_collection()

    filter_doc: dict = {"status": {"$nin": ["empty", "archived", "dismissed", "done"]}}
    if human_only:
        filter_doc["source"] = "human"
    if since:
        filter_doc["timestamp"] = {"$gte": since}
    if status:
        filter_doc["status"] = status
    if client:
        filter_doc["client"] = client

    pipeline = [
        {"$match": filter_doc},
        {"$addFields": {"_sort_ts": {"$ifNull": ["$last_activity_at", "$timestamp"]}}},
        {"$sort": {"_sort_ts": -1}},
        {"$limit": limit},
    ]
    docs = col.aggregate(pipeline)
    return [_doc_to_session(doc) for doc in docs]


def count_sessions(
    human_only: bool = True,
    since: datetime | None = None,
    status: str | None = None,
) -> int:
    """Count sessions matching the same filters as list_sessions (without limit)."""
    col = get_collection()

    filter_doc: dict = {"status": {"$nin": ["empty", "archived", "dismissed", "done"]}}
    if human_only:
        filter_doc["source"] = "human"
    if since:
        filter_doc["timestamp"] = {"$gte": since}
    if status:
        filter_doc["status"] = status

    return col.count_documents(filter_doc)


def get_session(session_id: str, refresh_metadata: bool = False) -> SessionInfo | None:
    """Get a single session by ID (or prefix)."""
    col = get_collection()
    doc = _find_session_doc(col, session_id)
    if not doc:
        return None
    if refresh_metadata:
        refreshed = refresh_session_metadata(doc["session_id"])
        if refreshed:
            return refreshed
    return _doc_to_session(doc)


def get_session_summary(session_id: str, refresh_metadata: bool = False) -> str | None:
    """Get a formatted summary string for a session."""
    session = get_session(session_id, refresh_metadata=refresh_metadata)
    if not session:
        return None
    return session.summary()


def link_session(
    session_id: str,
    project: str | None = None,
    task: str | None = None,
    task_id: str | None = None,
) -> bool:
    """Link a session to a project and/or task in MongoDB."""
    col = get_collection()
    session = get_session(session_id, refresh_metadata=True)
    if not session:
        return False

    update: dict = {}
    if project:
        update["project"] = project
    if task:
        update["task"] = task
    if task_id:
        update["task_id"] = task_id
    if not update:
        return False
    result = col.update_one(
        {"session_id": session.session_id},
        {"$set": update},
    )
    if result.matched_count:
        logger.info(
            f"Linked {session.session_id[:12]} → project={project}, task={task}, task_id={task_id}"
        )
    return result.matched_count > 0


def tag_session(session_id: str, tags: list[str]) -> bool:
    """Add tags to a session (appends, no duplicates)."""
    col = get_collection()
    session = get_session(session_id, refresh_metadata=True)
    if not session:
        return False

    result = col.update_one(
        {"session_id": session.session_id},
        {"$addToSet": {"tags": {"$each": tags}}},
    )
    if result.matched_count:
        logger.info(f"Tagged {session.session_id[:12]} with {tags}")
    return result.matched_count > 0


def update_session_status(session_id: str, status: str, wrapup_doc: str | None = None) -> bool:
    """Update session status (archived, completed, done, etc.)."""
    col = get_collection()
    session = get_session(session_id, refresh_metadata=True)
    if not session:
        return False

    update: dict = {"status": status}
    if wrapup_doc:
        update["wrapup_doc"] = wrapup_doc
    result = col.update_one(
        {"session_id": session.session_id},
        {"$set": update},
    )
    if result.matched_count:
        logger.info(f"Updated {session.session_id[:12]} status → {status}")
    return result.matched_count > 0


def fav_session(session_id: str) -> bool:
    """Mark a session as favorite (adds 'fav' tag)."""
    return tag_session(session_id, ["fav"])


def unfav_session(session_id: str) -> bool:
    """Remove favorite mark from a session."""
    col = get_collection()
    session = get_session(session_id, refresh_metadata=True)
    if not session:
        return False

    result = col.update_one(
        {"session_id": session.session_id},
        {"$pull": {"tags": "fav"}},
    )
    if result.matched_count:
        logger.info(f"Unfaved {session.session_id[:12]}")
    return result.matched_count > 0


def find_session_by_title(title: str) -> SessionInfo | None:
    """Find the most recent session with this exact title."""
    col = get_collection()
    doc = col.find_one({"title": title}, sort=[("timestamp", -1)])
    return _doc_to_session(doc) if doc else None


def find_current_session(
    cwd: str | None = None,
    first_message_substring: str | None = None,
    refresh_metadata: bool = False,
) -> SessionInfo | None:
    """Find the most recent human session matching CWD and/or first message text."""
    import os

    cwd = cwd or os.getcwd()
    col = get_collection()

    recency_sort = [("last_activity_at", -1), ("timestamp", -1)]

    if first_message_substring:
        doc = col.find_one(
            {
                "source": "human",
                "cwd": cwd,
                "first_message": {"$regex": first_message_substring, "$options": "i"},
            },
            sort=recency_sort,
        )
        if doc:
            if refresh_metadata:
                refreshed = refresh_session_metadata(doc["session_id"])
                if refreshed:
                    return refreshed
            return _doc_to_session(doc)
        doc = col.find_one(
            {
                "source": "human",
                "first_message": {"$regex": first_message_substring, "$options": "i"},
            },
            sort=recency_sort,
        )
        if doc:
            if refresh_metadata:
                refreshed = refresh_session_metadata(doc["session_id"])
                if refreshed:
                    return refreshed
            return _doc_to_session(doc)

    doc = col.find_one(
        {"source": "human", "cwd": cwd},
        sort=recency_sort,
    )
    if not doc:
        return None
    if refresh_metadata:
        refreshed = refresh_session_metadata(doc["session_id"])
        if refreshed:
            return refreshed
    return _doc_to_session(doc)


def list_fav_sessions(limit: int = 20) -> list[SessionInfo]:
    """List sessions tagged as favorite."""
    col = get_collection()
    docs = col.find({"tags": "fav"}).sort("timestamp", -1).limit(limit)
    return [_doc_to_session(doc) for doc in docs]


def set_session_title(
    session_id: str,
    title: str,
    cwd: str | None = None,
) -> SessionInfo | None:
    """Set a human title for a session while preserving the real resumeable UUID."""
    col = get_collection()
    doc = _find_session_doc(col, session_id)
    if not doc:
        return None

    session = _doc_to_session(doc)
    normalized_title = _normalize_session_title(title)
    update: dict[str, str] = {
        "title": normalized_title,
        "title_source": "manual",
    }

    if session.client == "claude":
        try:
            claude_rename_session(
                session.session_id,
                normalized_title,
                directory=cwd or session.cwd,
            )
            update = {
                "title": normalized_title,
                "title_source": "claude_custom_title",
                "claude_custom_title": normalized_title,
            }
        except Exception as exc:
            logger.warning(
                f"Failed to rename Claude session {session.session_id[:12]} in storage: {exc}"
            )

    col.update_one({"session_id": session.session_id}, {"$set": update})
    doc.update(update)

    refreshed = refresh_session_metadata(session.session_id)
    if refreshed:
        return refreshed
    return _doc_to_session(doc)


def launch_session(
    prompt: str,
    system_prompt: str | None = None,
    cwd: str | None = None,
    title: str | None = None,
    project: str | None = None,
    task: str | None = None,
    client: str = "claude",
    model: str | None = None,
    headless: bool = True,
    dangerously_skip_permissions: bool = False,
    source: str | None = None,
) -> dict:
    """Launch an AI session, register it, and optionally link to project/task.

    `headless` controls execution semantics (fire-and-forget vs wait for response).
    `source` controls the registry tag — pass "ai" when this call originates from
    inside another AI session so textvault and patchbay search filters can
    exclude turns from this session out of the "user-sent" slice. If None, falls
    back to the legacy headless-derived default (headless → "human", else "ai").
    """
    import asyncio
    from calmlib.utils.agent_launcher import AgentClient, start_agent_chat

    client_enum = AgentClient(client)

    allowed_tools = None
    if dangerously_skip_permissions:
        allowed_tools = ["Read", "Glob", "Grep", "Bash", "Edit", "Write", "Task",
                         "Agent", "NotebookEdit", "WebFetch", "WebSearch"]

    result = asyncio.run(start_agent_chat(
        text=prompt,
        client=client_enum,
        cwd=cwd,
        system_prompt=system_prompt,
        session_title=title,
        allow_writes=True,
        model=model,
        allowed_tools=allowed_tools,
        show_progress=True,
        session_only=headless,
    ))

    # start_agent_chat sets source = "human" if session_only else "ai" — that
    # conflates "fire-and-forget" with "who initiated me". When the caller
    # supplies an explicit source, patch the registry record so the right tag
    # sticks regardless of headless.
    legacy_source = "human" if headless else "ai"
    if source is not None and source != legacy_source:
        try:
            from calmlib.utils.patchbay.core.db import get_collection

            get_collection().update_one(
                {"session_id": result.session_id},
                {"$set": {"source": source}},
            )
        except Exception as e:
            logger.warning(f"failed to override session source to {source}: {e}")

    if project or task:
        link_session(result.session_id, project=project, task=task)

    resume_cmd = result.resume_command
    logger.info(f"Launched session: {title or result.session_id[:12]}")
    logger.info(f"Resume: {resume_cmd}")

    return {
        "session_id": result.session_id,
        "resume_command": resume_cmd,
        "title": title or result.session_id[:12],
        "created_new": True,
    }


def semantic_search_sessions(
    query: str,
    limit: int = 10,
    hit_budget: int | None = None,
    human_only: bool = True,
    since: datetime | None = None,
) -> list[dict]:
    """Semantic search over claude_code turn-pair embeddings, aggregated by session.

    Each result: {"session": SessionInfo, "sim": float, "matches": int, "preview": str}.
    Sorted by max turn similarity per session.
    """
    from calmlib.textvault import TextVault
    from calmlib.textvault.embeddings import vector_search_claude_code

    hit_budget = hit_budget or max(limit * 10, 50)
    with TextVault() as vault:
        hits = vector_search_claude_code(vault, query, limit=hit_budget, since=since)

    by_session: dict[str, dict] = {}
    for h in hits:
        md = h.get("metadata") or {}
        sid = md.get("session_id")
        if not sid:
            continue
        sim = float(h.get("sim") or 0.0)
        entry = by_session.setdefault(sid, {"sim": 0.0, "matches": 0, "preview": ""})
        entry["matches"] += 1
        if sim > entry["sim"]:
            entry["sim"] = sim
            entry["preview"] = (h.get("text") or "").replace("\n", " ")[:200]
    if not by_session:
        return []

    col = get_collection()
    docs = col.find({"session_id": {"$in": list(by_session.keys())}})

    results: list[dict] = []
    for doc in docs:
        sid = doc.get("session_id")
        if human_only and doc.get("source") != "human":
            continue
        if doc.get("status") in ("dismissed", "empty"):
            continue
        info = by_session[sid]
        results.append({
            "session": _doc_to_session(doc),
            "sim": info["sim"],
            "matches": info["matches"],
            "preview": info["preview"],
        })

    results.sort(key=lambda r: r["sim"], reverse=True)
    return results[:limit]


def list_unlinked_sessions(
    days: int = 7,
    limit: int = 50,
    human_only: bool = True,
) -> list[SessionInfo]:
    """List sessions with no project and no task link."""
    col = get_collection()

    filter_doc: dict = {
        "status": {"$nin": ["archived", "dismissed", "empty", "done"]},
        "$and": [
            {"$or": [{"project": {"$exists": False}}, {"project": None}]},
            {"$or": [{"task": {"$exists": False}}, {"task": None}]},
        ],
    }
    if human_only:
        filter_doc["source"] = "human"
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        filter_doc["timestamp"] = {"$gte": cutoff}

    docs = col.find(filter_doc).sort("timestamp", -1).limit(limit)
    return [_doc_to_session(doc) for doc in docs]
