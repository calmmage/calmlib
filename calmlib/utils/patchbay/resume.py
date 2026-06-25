"""Patchbay resume — resume or fork existing completed sessions."""

import os
from datetime import datetime

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
)
from loguru import logger

from calmlib.utils.claude_code.sdk import resolve_claude_code_model
from calmlib.utils.patchbay.query import get_collection


async def resume_session(
    session_id: str,
    message: str,
    cwd: str | None = None,
    model: str | None = None,
) -> str:
    """Resume an existing completed session and send a message. Returns response text."""
    cwd = cwd or os.getcwd()
    resolved_model = resolve_claude_code_model(model)

    options = ClaudeAgentOptions(
        cwd=cwd,
        allowed_tools=["Read", "Glob", "Grep", "Bash", "Edit", "Write", "Task"],
        model=resolved_model,
        resume=session_id,
    )

    client = ClaudeSDKClient(options=options)
    await client.connect()

    logger.info(f"Resuming session {session_id[:12]}")
    await client.query(message)

    response_parts: list[str] = []
    cost = 0.0

    async for msg in client.receive_response():
        if isinstance(msg, AssistantMessage) and hasattr(msg, "content"):
            for block in msg.content:
                if hasattr(block, "text"):
                    response_parts.append(block.text)
        elif isinstance(msg, ResultMessage):
            if hasattr(msg, "total_cost_usd") and msg.total_cost_usd:
                cost = msg.total_cost_usd

    await client.disconnect()

    # Update MongoDB
    col = get_collection()
    col.update_one(
        {"session_id": session_id},
        {"$set": {"last_resumed": datetime.now()}, "$inc": {"resume_count": 1}},
    )
    logger.info(f"Resumed {session_id[:12]}, got {len(''.join(response_parts))} chars (${cost:.4f})")

    return "\n".join(response_parts)


async def fork_session(
    session_id: str,
    message: str,
    cwd: str | None = None,
    model: str | None = None,
    task_description: str | None = None,
) -> tuple[str, str]:
    """Fork a session — resume it but create a new session ID. Returns (new_session_id, response_text)."""
    cwd = cwd or os.getcwd()
    resolved_model = resolve_claude_code_model(model)

    options = ClaudeAgentOptions(
        cwd=cwd,
        allowed_tools=["Read", "Glob", "Grep", "Bash", "Edit", "Write", "Task"],
        model=resolved_model,
        resume=session_id,
    )
    options.fork_session = True

    client = ClaudeSDKClient(options=options)
    await client.connect()

    logger.info(f"Forking session {session_id[:12]}")
    await client.query(message)

    response_parts: list[str] = []
    new_session_id = None
    cost = 0.0

    async for msg in client.receive_response():
        if isinstance(msg, SystemMessage):
            sid = msg.data.get("session_id")
            if sid:
                new_session_id = sid
        elif isinstance(msg, AssistantMessage) and hasattr(msg, "content"):
            for block in msg.content:
                if hasattr(block, "text"):
                    response_parts.append(block.text)
        elif isinstance(msg, ResultMessage):
            if hasattr(msg, "total_cost_usd") and msg.total_cost_usd:
                cost = msg.total_cost_usd
            if hasattr(msg, "session_id") and msg.session_id:
                new_session_id = new_session_id or msg.session_id

    await client.disconnect()

    if not new_session_id:
        raise RuntimeError("Failed to get new session ID from forked session")

    # Register new session in MongoDB
    col = get_collection()
    record = {
        "session_id": new_session_id,
        "client": "claude",
        "source": "ai",
        "cwd": cwd,
        "timestamp": datetime.now(),
        "forked_from": session_id,
        "total_cost_usd": cost,
    }
    if task_description:
        record["task_description"] = task_description
    col.update_one(
        {"session_id": new_session_id},
        {"$set": record},
        upsert=True,
    )
    logger.info(f"Forked {session_id[:12]} → {new_session_id[:12]} (${cost:.4f})")

    return new_session_id, "\n".join(response_parts)
