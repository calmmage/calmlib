"""Environment key lookup helpers.

Keychain lookup attempts append value-free diagnostics to
`~/Library/Logs/calmmage/env-discovery.log` by default. Override the path with
`CALMMAGE_ENV_DISCOVERY_DIAG_LOG`, or set it to `off`/`0`/`false` to disable.
"""

import base64
import json
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values, load_dotenv
from loguru import logger

ENV_DISCOVERY_DIAG_LOG_ENV = "CALMMAGE_ENV_DISCOVERY_DIAG_LOG"
DEFAULT_ENV_DISCOVERY_DIAG_LOG = (
    Path.home() / "Library" / "Logs" / "calmmage" / "env-discovery.log"
)
_DISABLE_DIAG_LOG_VALUES = {"0", "false", "no", "off", "none"}
_SENSITIVE_ARG_MARKERS = (
    "api-key",
    "apikey",
    "authorization",
    "bearer",
    "key",
    "password",
    "passwd",
    "secret",
    "token",
)
_diag_notice_emitted = False


def _env_discovery_diag_log_path() -> Path | None:
    configured = os.getenv(ENV_DISCOVERY_DIAG_LOG_ENV)
    if configured is None:
        return DEFAULT_ENV_DISCOVERY_DIAG_LOG

    configured = configured.strip()
    if configured.lower() in _DISABLE_DIAG_LOG_VALUES:
        return None
    if not configured:
        return DEFAULT_ENV_DISCOVERY_DIAG_LOG
    return Path(configured).expanduser()


def _redacted_argv() -> list[str]:
    redacted: list[str] = []
    redact_next = False

    for arg in sys.argv:
        if redact_next:
            redacted.append("[REDACTED]")
            redact_next = False
            continue

        lower = arg.lower()
        marker_hit = any(marker in lower for marker in _SENSITIVE_ARG_MARKERS)
        if marker_hit and "=" in arg:
            name, _value = arg.split("=", 1)
            redacted.append(f"{name}=[REDACTED]")
            continue
        if marker_hit and lower.startswith("-"):
            redacted.append(arg)
            redact_next = True
            continue

        redacted.append(arg)

    return redacted


def _write_env_discovery_diag(event: str, key: str, **extra: object) -> None:
    log_path = _env_discovery_diag_log_path()
    if log_path is None:
        return

    try:
        _emit_env_discovery_diag_notice_once(log_path)
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
            "service": "calmmage",
            "key": key,
            "pid": os.getpid(),
            "ppid": os.getppid(),
            "cwd": os.getcwd(),
            "argv": _redacted_argv(),
            **extra,
        }
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
    except Exception:
        # Diagnostics must never interfere with secret lookup.
        return


def _emit_env_discovery_diag_notice_once(log_path: Path) -> None:
    global _diag_notice_emitted
    if _diag_notice_emitted:
        return

    _diag_notice_emitted = True
    try:
        sys.stderr.write(
            "calmlib env_discovery: keychain access breadcrumbs are logged at "
            f"{log_path}. Set {ENV_DISCOVERY_DIAG_LOG_ENV}=off to disable.\n"
        )
        sys.stderr.flush()
    except Exception:
        return


def _keychain_lookup_start(key: str, reason: str) -> None:
    _write_env_discovery_diag("keychain_lookup_start", key, reason=reason)


def _keychain_lookup_result(key: str, reason: str, value: str | None) -> None:
    _write_env_discovery_diag(
        "keychain_lookup_result",
        key,
        reason=reason,
        result="found" if value is not None else "missing",
    )


def _keychain_lookup_error(key: str, reason: str, error: Exception) -> None:
    _write_env_discovery_diag(
        "keychain_lookup_error",
        key,
        reason=reason,
        error_type=type(error).__name__,
    )


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


def _load_from_encrypted_file(key: str) -> str | None:
    """Load a key from encrypted file using master password."""
    encrypted_file = Path.home() / ".env.enc"
    if not encrypted_file.exists():
        return None

    # Get master password from env or keychain
    master_password = os.getenv("CALMMAGE_ENV_PASSWORD")
    if not master_password:
        try:
            import keyring

            _keychain_lookup_start(
                "CALMMAGE_ENV_PASSWORD", "encrypted_file_master_password"
            )
            master_password = keyring.get_password("calmmage", "CALMMAGE_ENV_PASSWORD")
            _keychain_lookup_result(
                "CALMMAGE_ENV_PASSWORD",
                "encrypted_file_master_password",
                master_password,
            )
        except Exception as e:
            _keychain_lookup_error(
                "CALMMAGE_ENV_PASSWORD", "encrypted_file_master_password", e
            )
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


def find_env_key(key: str, default: str | None = None) -> str | None:
    """Find an environment variable key, with fallback to keychain and .env files.

    Also tries CALMMAGE_ prefix if the bare key is not found.
    """
    result = _find_env_key_exact(key, default)
    if result is not None:
        return result
    # Try with CALMMAGE_ prefix if not already prefixed
    if not key.startswith("CALMMAGE_"):
        result = _find_env_key_exact(f"CALMMAGE_{key}", default)
        if result is not None:
            return result
    return default


def _find_env_key_exact(key: str, default: str | None = None) -> str | None:
    """Find an environment variable key exactly as specified."""

    # Step 1: Check if the key exists in the environment
    value = os.getenv(key)
    if value is not None:
        return value

    # Step 2: Check macOS Keychain (for secure storage)
    try:
        import keyring

        _keychain_lookup_start(key, "direct_key_lookup")
        keychain_value = keyring.get_password("calmmage", key)
        _keychain_lookup_result(key, "direct_key_lookup", keychain_value)
        if keychain_value is not None:
            return keychain_value
    except Exception as e:
        _keychain_lookup_error(key, "direct_key_lookup", e)
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


def find_calmmage_env_key(key: str, default: str | None = None) -> str:
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


def get_calmmage_venv_path() -> str | None:
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
