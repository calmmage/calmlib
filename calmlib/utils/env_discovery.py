# todo: introduce 'find_env_key' instead - with backup lookup feature
from dotenv import dotenv_values
from pathlib import Path
import os


def find_env_key(key: str, default: str = None) -> str:
    """Find an environment variable key, with a fallback to a default value."""

    # Check if the key exists in the environment
    value = os.getenv(key)

    if value is not None:
        return value

    # step 2: check ./.env
    if Path(".env").exists():
        env_values = dotenv_values(".env")
        if key in env_values:
            return env_values[key]

    # step 3: check ~/.env
    env_path = Path.home() / ".env"
    if env_path.exists():
        env_values = dotenv_values(env_path)
        if key in env_values:
            return env_values[key]

    # If not found, return the default value if provided
    return default

def load_global_env():
    """Load environment variables from ~/.env"""
    from dotenv import load_dotenv
    from pathlib import Path

    env_path = Path.home() / ".env"
    load_dotenv(env_path)


def find_calmmage_env_key(key: str, default: str = None) -> str:
    """Find a calmmage-specific environment key with setup hint if missing."""
    value = find_env_key(key, default)
    if value is None and default is None:
        raise ValueError(
            f"Calmmage environment key '{key}' not found.\n"
            f"Run: uv run typer tools/env_setup_script/cli.py run setup"
        )
    return value
