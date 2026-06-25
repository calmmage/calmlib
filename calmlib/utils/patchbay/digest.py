"""Patchbay digest — read and summarize session content via SDK."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from loguru import logger
from pydantic import BaseModel

if TYPE_CHECKING:
    pass


class DigestMode(str, Enum):
    FULL = "full"  # all messages
    USER_ONLY = "user_only"  # only user messages
    TEXT_ONLY = "text_only"  # AI text responses, excluding tool use / code blocks


class SessionDigest(BaseModel):
    session_id: str
    message_count: int = 0
    user_message_count: int = 0
    assistant_message_count: int = 0
    messages_preview: str = ""  # raw messages for inspection
    summary: str | None = None  # LLM-generated summary


def _extract_text_from_content(content) -> str:
    """Extract text from message content, handling various formats."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", ""))
                elif block.get("type") == "tool_use":
                    # Skip tool use blocks in text_only mode, include name in other modes
                    parts.append(f"[tool: {block.get('name', '?')}]")
                elif block.get("type") == "tool_result":
                    parts.append("[tool result]")
            elif hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)
    return str(content)


def _extract_text_only(content) -> str | None:
    """Extract only AI text, excluding tool calls and code. Returns None if no text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    parts.append(text)
            elif hasattr(block, "type") and block.type == "text":
                text = block.text.strip()
                if text:
                    parts.append(text)
        return "\n".join(parts) if parts else None
    return str(content)


def get_session_messages_raw(session_id: str, cwd: str | None = None) -> list[dict]:
    """Read messages from a session via claude-agent-sdk.

    Returns list of dicts with 'type' (user/assistant) and 'message' (with role + content).
    """
    from claude_agent_sdk import get_session_messages

    if not cwd:
        from calmlib.utils.patchbay.query import get_session
        s = get_session(session_id)
        cwd = s.cwd if s else None

    try:
        sdk_msgs = get_session_messages(session_id, directory=cwd)
        return [
            {"type": m.type, "message": m.message}
            for m in sdk_msgs
        ]
    except Exception as e:
        logger.warning(f"SDK get_session_messages failed: {e}")
        return []


def _is_real_human_message(content: str) -> bool:
    """Filter out skill loads, hooks, and empty messages."""
    if not content or len(content.strip()) < 20:
        return False
    if content.startswith("Base directory for this skill:"):
        return False
    if content.startswith("<local-command-stdout>"):
        return False
    return True


def get_session_digest(
    session_id: str,
    mode: DigestMode = DigestMode.TEXT_ONLY,
    summarize: bool = True,
    summary_model: str = "haiku",
    max_messages: int | None = None,
) -> SessionDigest:
    """Read a session's messages and optionally summarize.

    Args:
        session_id: Session ID (or prefix)
        mode: What to include — full, user_only, or text_only (AI text minus tool use)
        summarize: Whether to generate an LLM summary
        summary_model: Model for summarization (default: haiku for cheapness)
        max_messages: Limit messages read (None = all)
    """
    # Resolve prefix
    from calmlib.utils.patchbay.query import get_session
    session = get_session(session_id)
    if not session:
        return SessionDigest(session_id=session_id)

    full_id = session.session_id
    raw_messages = get_session_messages_raw(full_id, cwd=session.cwd)

    if max_messages:
        raw_messages = raw_messages[:max_messages]

    # Count and filter messages
    user_msgs = []
    assistant_msgs = []
    filtered_parts = []

    for msg in raw_messages:
        msg_type = msg.get("type", "")
        message_data = msg.get("message", msg)
        content = message_data.get("content", "")

        if msg_type == "user":
            text = _extract_text_from_content(content)
            if _is_real_human_message(text):
                user_msgs.append(text)
                if mode in (DigestMode.FULL, DigestMode.USER_ONLY):
                    filtered_parts.append(f"[USER]: {text[:500]}")

        elif msg_type == "assistant":
            if mode == DigestMode.TEXT_ONLY:
                text = _extract_text_only(content)
                if text:
                    assistant_msgs.append(text)
                    filtered_parts.append(f"[AI]: {text[:500]}")
            elif mode == DigestMode.FULL:
                text = _extract_text_from_content(content)
                if text.strip():
                    assistant_msgs.append(text)
                    filtered_parts.append(f"[AI]: {text[:500]}")

    preview = "\n\n".join(filtered_parts)

    digest = SessionDigest(
        session_id=full_id,
        message_count=len(raw_messages),
        user_message_count=len(user_msgs),
        assistant_message_count=len(assistant_msgs),
        messages_preview=preview,
    )

    # Summarize with LLM
    if summarize and preview.strip():
        try:
            import asyncio
            from calmlib.llm import aquery_llm_text

            prompt = f"""Summarize this AI coding session. Answer these questions:
1. What was the user trying to accomplish?
2. What was actually done/built?
3. Did the conversation stay on track or drift?
4. What's the current state — finished, abandoned, or in-progress?

Session title: {session.title or 'untitled'}
Topics: {session.topics_short or 'none'}

Conversation:
{preview[:4000]}"""

            summary = asyncio.get_event_loop().run_until_complete(
                aquery_llm_text(prompt, model=summary_model)
            )
            digest.summary = summary
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            digest.summary = f"[summary failed: {e}]"

    return digest
