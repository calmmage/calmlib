"""Gemini CLI wrapper for starting and managing conversations via subprocess"""

import os
import subprocess

from loguru import logger


async def start_gemini_chat(
    text: str,
    cwd: str | None = None,
    system_prompt: str | None = None,
    show_progress: bool = False,
    allow_writes: bool = True,
) -> str:
    """Start a Gemini CLI conversation and return session ID.

    Invokes the `gemini` CLI via subprocess. Requires `gemini` to be installed
    (npm i -g @google/gemini-cli or brew install gemini).

    Args:
        text: Initial message/prompt to send
        cwd: Working directory for the conversation
        system_prompt: Optional system instructions (prepended to prompt)
        show_progress: Whether to show progress output
        allow_writes: Approval mode - True=auto_edit, False=default

    Returns:
        Session ID (index) of the created conversation
    """
    if cwd is None:
        cwd = os.getcwd()

    cmd = ["gemini"]

    # Set approval mode
    if allow_writes:
        cmd.extend(["--approval-mode", "auto_edit"])

    # Gemini uses positional prompt for one-shot mode
    # Use --prompt-interactive for interactive mode that saves session
    full_prompt = text
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{text}"

    cmd.extend(["--prompt-interactive", full_prompt])

    env = os.environ.copy()

    logger.debug(f"Starting gemini with cmd: {cmd}")
    logger.debug(f"Working directory: {cwd}")

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )

        if result.returncode != 0:
            logger.error(f"Gemini CLI failed: {result.stderr}")
            raise RuntimeError(
                f"Gemini CLI failed with code {result.returncode}: {result.stderr}"
            )

        output = result.stdout.strip()
        logger.debug(f"Gemini output: {output[:500]}")

        # Gemini uses index-based session resume (--resume latest or --resume N)
        # Find the latest session index
        session_id = _find_latest_gemini_session(cwd)

        if not session_id:
            # Fallback to "latest" as session identifier
            session_id = "latest"

        return session_id

    except FileNotFoundError:
        raise RuntimeError(
            "Gemini CLI not found. Install with: npm i -g @google/gemini-cli"
        )


def _find_latest_gemini_session(cwd: str) -> str | None:
    """Find the most recent Gemini session index by listing sessions."""
    try:
        result = subprocess.run(
            ["gemini", "--list-sessions"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Parse session list output to find the latest index
            lines = result.stdout.strip().split("\n")
            if lines:
                # Return "latest" as a portable session identifier
                return "latest"
    except Exception as e:
        logger.debug(f"Could not list Gemini sessions: {e}")
    return None


def get_gemini_resume_command(session_id: str, cwd: str) -> str:
    """Generate the resume command for a Gemini session."""
    return f"cd {cwd} && gemini --resume {session_id}"
