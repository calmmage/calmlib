"""Claude SDK utilities for starting and managing Claude Code conversations"""

import os

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, SystemMessage
from loguru import logger
from tqdm import tqdm


async def start_claude_chat(
    text: str,
    cwd: str | None = None,
    system_prompt: str | None = None,
    show_progress: bool = False,
    allowed_tools: list[str] | None = None,
    allow_writes: bool = True,
) -> str:
    """Start a Claude Code conversation and return session ID

    Args:
        text: Initial message to send
        cwd: Working directory for the conversation (defaults to current directory)
        system_prompt: Optional system prompt to append
        show_progress: Whether to show tqdm progress bar (default: False)
        allowed_tools: List of allowed tools (overrides allow_writes if provided)
        allow_writes: Whether to allow write tools (only used if allowed_tools is None)

    Returns:
        Session ID of the created conversation
    """
    if cwd is None:
        cwd = os.getcwd()

    if allowed_tools is None:
        if allow_writes:
            allowed_tools = ["Read", "Glob", "Grep", "Bash", "Edit", "Write", "Task"]
        else:
            allowed_tools = ["Read", "Glob", "Grep", "Bash", "Task"]

    options = ClaudeAgentOptions(
        cwd=cwd,
        allowed_tools=allowed_tools,
    )
    if system_prompt:
        options.append_system_prompt = system_prompt

    cc = ClaudeSDKClient(options=options)
    await cc.connect()
    await cc.query(text)

    session_id = None
    with tqdm(
        desc="Waiting for Claude response", unit=" messages", disable=not show_progress
    ) as pbar:
        async for m in cc.receive_response():
            pbar.update(1)
            if isinstance(m, SystemMessage):
                session_id = m.data.get("session_id")
                if session_id:
                    logger.debug(f"Claude Code session ID detected: {session_id}")
                    if show_progress:
                        pbar.set_description("Session ID received")

    if not session_id:
        raise RuntimeError("Failed to get session ID from Claude conversation")

    return session_id
