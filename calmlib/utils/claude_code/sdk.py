"""Claude SDK utilities for starting and managing Claude Code conversations"""

import os

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    SystemMessage,
    rename_session as claude_rename_session,
)
from loguru import logger
from tqdm import tqdm

# Claude Code model shortcuts → full model IDs
# These match what `claude --model <alias>` accepts
CLAUDE_CODE_MODEL_SHORTCUTS = {
    # Current generation (4.6)
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5",
    # Explicit version aliases
    "opus-4.6": "claude-opus-4-6",
    "sonnet-4.6": "claude-sonnet-4-6",
    "haiku-4.5": "claude-haiku-4-5",
    # Previous generation
    "opus-4": "claude-opus-4-20250514",
    "sonnet-4": "claude-sonnet-4-20250514",
    "sonnet-4.5": "claude-sonnet-4-5-20250514",
}


def resolve_claude_code_model(model: str | None) -> str | None:
    """Resolve a model shortcut to a full Claude Code model ID.

    Accepts shortcuts like "sonnet", "opus", "haiku", "sonnet-4.6"
    or full IDs like "claude-sonnet-4-6" (passed through as-is).
    """
    if model is None:
        return None
    return CLAUDE_CODE_MODEL_SHORTCUTS.get(model.lower(), model)


async def start_claude_chat(
    text: str,
    cwd: str | None = None,
    system_prompt: str | None = None,
    show_progress: bool = False,
    allowed_tools: list[str] | None = None,
    allow_writes: bool = True,
    model: str | None = None,
    resume: str | None = None,
    session_title: str | None = None,
    session_only: bool = False,
) -> str:
    """Start a Claude Code conversation and return session ID

    Args:
        text: Initial message to send
        cwd: Working directory for the conversation (defaults to current directory)
        system_prompt: Optional system prompt to append
        show_progress: Whether to show tqdm progress bar (default: False)
        allowed_tools: List of allowed tools (overrides allow_writes if provided)
        allow_writes: Whether to allow write tools (only used if allowed_tools is None)
        model: Model shortcut or full ID (e.g. "sonnet", "claude-sonnet-4-6")
        resume: Session ID to resume a previous conversation
        session_title: Human title to apply to the Claude session
        session_only: If True, return immediately after getting session_id (don't wait for full response)

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

    resolved_model = resolve_claude_code_model(model)
    if resolved_model and resolved_model != model:
        logger.debug(f"Resolved model shortcut: {model} → {resolved_model}")

    options = ClaudeAgentOptions(
        cwd=cwd,
        allowed_tools=allowed_tools,
        model=resolved_model,
        resume=resume,
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
                    # Note: don't break early — session must finish writing to disk
                    # before it can be resumed

    if not session_id:
        raise RuntimeError("Failed to get session ID from Claude conversation")

    if session_title and session_title.strip():
        try:
            claude_rename_session(session_id, session_title.strip(), directory=cwd)
        except Exception as exc:
            logger.warning(f"Failed to rename Claude session {session_id[:12]}: {exc}")

    return session_id
