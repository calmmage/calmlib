import base64
import json
import os
import traceback
from pathlib import Path
from typing import Optional

import keyring
from dotenv import dotenv_values, load_dotenv
from loguru import logger


def _generate_key_from_password(password: str) -> bytes:
    """Generate a Fernet key from password using PBKDF2."""
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        # Use a fixed salt for consistency
        salt = b"calmmage_salt_123456"  # 16+ bytes recommended
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    except ImportError:
        # cryptography not available
        return None


def _load_from_encrypted_file(key: str) -> Optional[str]:
    """Load a key from encrypted file using master password."""
    encrypted_file = Path.home() / ".env.enc"
    if not encrypted_file.exists():
        return None

    # Get master password from env or keychain
    master_password = os.getenv("CALMMAGE_ENV_PASSWORD")
    if not master_password:
        try:
            master_password = keyring.get_password("calmmage", "CALMMAGE_ENV_PASSWORD")
        except Exception:
            return None

    if not master_password:
        return None

    try:
        from cryptography.fernet import Fernet

        # Generate encryption key from password
        encryption_key = _generate_key_from_password(master_password)
        if not encryption_key:
            return None

        f = Fernet(encryption_key)

        # Read and decrypt file
        encrypted_data = encrypted_file.read_bytes()
        decrypted_data = f.decrypt(encrypted_data)
        secrets = json.loads(decrypted_data.decode())

        return secrets.get(key)

    except Exception:
        # Silently fail if decryption fails
        logger.debug(f"Failed to decrypt {key} from encrypted file")
        traceback.print_exc()
        return None


def find_env_key(key: str, default: Optional[str] = None) -> Optional[str]:
    """Find an environment variable key, with fallback to keychain and .env files."""

    # Step 1: Check if the key exists in the environment
    value = os.getenv(key)
    if value is not None:
        return value

    # Step 2: Check macOS Keychain (for secure storage)
    try:
        keychain_value = keyring.get_password("calmmage", key)
        if keychain_value is not None:
            return keychain_value
    except Exception:
        # Keyring not available or other error, continue to .env files
        logger.debug(f"Didn't find {key} in keychain")

    # Step 3: Check encrypted file (~/.env.enc)
    encrypted_value = _load_from_encrypted_file(key)
    if encrypted_value is not None:
        return encrypted_value

    # Step 4: Check ./.env
    if Path(".env").exists():
        env_values = dotenv_values(".env")
        if key in env_values:
            return env_values[key]

    # Step 5: Check ~/.env
    env_path = Path.home() / ".env"
    if env_path.exists():
        env_values = dotenv_values(env_path)
        if key in env_values:
            return env_values[key]

    # If not found, return the default value if provided
    return default


def load_global_env():
    """Load environment variables from ~/.env"""
    env_path = Path.home() / ".env"
    load_dotenv(env_path)


def find_calmmage_env_key(key: str, default: Optional[str] = None) -> str:
    """Find a calmmage-specific environment key with setup hint if missing."""
    value = find_env_key(key, default)
    if value is None:
        value = default
    if value is None:
        raise ValueError(
            f"Calmmage environment key '{key}' not found.\n"
            f"Run: uv run typer tools/env_setup_script/cli.py run setup"
        )
    return value


def set_calmmage_env_key(key: str, value: str) -> bool:
    """Set a calmmage environment key using the configured storage mode.

    Args:
        key: The environment variable name
        value: The value to set

    Returns:
        bool: True if successful, False otherwise

    Example:
        >>> set_calmmage_env_key("MY_API_KEY", "secret_value")
        True
    """
    try:
        # Import here to avoid circular dependency
        from tools.automations.env_setup_script.core import (
            EnvManager,
            SecretStorageMode,
        )

        # Use encrypted file mode by default (most secure)
        manager = EnvManager(storage_mode=SecretStorageMode.ENCRYPTED_FILE)
        return manager.set_env_var(key, value)
    except Exception as e:
        logger.error(f"Failed to set calmmage env key '{key}': {e}")
        return False


def get_calmmage_venv_path() -> Optional[str]:
    """Get the path to the calmmage venv."""
    if os.getenv("CALMMAGE_VENV_PATH"):
        return os.getenv("CALMMAGE_VENV_PATH")
    # use ~/.dev-env-location
    dev_env_location = Path.home() / ".dev-env-location"
    if dev_env_location.exists():
        text = dev_env_location.read_text()
        for line in text.splitlines():
            if line.startswith("export CALMMAGE_VENV_PATH="):
                return line.split("=")[1].strip()
    return None
