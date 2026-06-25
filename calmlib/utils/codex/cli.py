"""Codex CLI wrapper for starting and managing conversations via subprocess"""

import json
import os
import subprocess

from loguru import logger


async def start_codex_chat(
    text: str,
    cwd: str | None = None,
    system_prompt: str | None = None,
    show_progress: bool = False,
    allow_writes: bool = True,
) -> str:
    """Start a Codex CLI conversation and return session ID.

    Uses `codex exec --json` to run non-interactively and parse the
    thread_id from structured JSONL output.

    Args:
        text: Initial message/prompt to send
        cwd: Working directory for the conversation
        system_prompt: Optional system instructions (prepended to prompt)
        show_progress: Whether to show progress output
        allow_writes: True=full-auto sandbox, False=read-only sandbox

    Returns:
        Thread ID (session ID) of the created conversation
    """
    if cwd is None:
        cwd = os.getcwd()

    cmd = ["codex", "exec", "--json"]

    if allow_writes:
        cmd.append("--full-auto")
    else:
        cmd.extend(["--sandbox", "read-only"])

    full_prompt = text
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{text}"

    cmd.append(full_prompt)

    logger.debug(f"Starting codex with cmd: {cmd}")
    logger.debug(f"Working directory: {cwd}")

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            env=os.environ.copy(),
        )

        if result.returncode != 0:
            logger.error(f"Codex CLI failed: {result.stderr}")
            raise RuntimeError(
                f"Codex CLI failed with code {result.returncode}: {result.stderr}"
            )

        # Parse JSONL output for thread_id
        session_id = _parse_thread_id(result.stdout)

        if not session_id:
            logger.debug(f"Codex output: {result.stdout[:500]}")
            raise RuntimeError("Failed to get session ID from Codex output")

        return session_id

    except FileNotFoundError:
        raise RuntimeError(
            "Codex CLI not found. Install with: npm i -g @openai/codex or brew install --cask codex"
        )


def _parse_thread_id(jsonl_output: str) -> str | None:
    """Extract thread_id from codex exec --json JSONL output."""
    for line in jsonl_output.strip().split("\n"):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "thread.started" and "thread_id" in event:
                return event["thread_id"]
        except json.JSONDecodeError:
            continue
    return None


def get_codex_resume_command(session_id: str, cwd: str) -> str:
    """Generate the resume command for a Codex session."""
    return f"cd {cwd} && codex resume {session_id}"
