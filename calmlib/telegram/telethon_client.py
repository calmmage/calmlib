"""
Simple telethon client utilities for calmmage ecosystem.

Provides hassle-free access to authenticated Telethon clients for
primary and secondary Telegram accounts. Session files are stored
in a stable location and authentication is handled interactively when needed.
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Optional

from async_lru import alru_cache
from loguru import logger
from telethon import TelegramClient
from telethon.types import User

from calmlib.utils.env_discovery import find_calmmage_env_key

try:
    import fcntl  # POSIX file locking
except Exception:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore
from calmlib.utils.user_interactions import ask_user

# Session storage location - using ~/.calmmage/telethon_sessions
SESSIONS_DIR = Path.home() / ".calmmage" / "telethon_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


async def authenticate_telethon_client(
    api_id: int,
    api_hash: str,
    phone: str,
    session_name: str,
    session_dir: Optional[Path] = None,
    password_env_key: Optional[str] = None,
    lock_timeout_sec: float = 120.0,
    lock_poll_sec: float = 0.5,
) -> TelegramClient:
    """
    Core authentication utility for Telethon clients.

    This is the shared authentication logic used by all telethon client functions.
    Handles interactive authentication, 2FA, and session persistence.

    Args:
        api_id: Telegram API ID
        api_hash: Telegram API Hash
        phone: Phone number for authentication
        session_name: Name for the session file (e.g., "primary", "user_12345")
        session_dir: Directory to store session files (defaults to SESSIONS_DIR)
        password_env_key: Environment variable name for 2FA password (optional)

    Returns:
        Authenticated TelegramClient

    Raises:
        ValueError: If authentication fails
    """
    if session_dir is None:
        session_dir = SESSIONS_DIR

    session_path = session_dir / session_name
    session_file = session_path.with_suffix(".session")

    client = TelegramClient(str(session_path), api_id, api_hash)

    # Prevent concurrent usage of the same session by multiple processes
    lock_file = session_path.with_suffix(".session.lock")
    lock_fh = None
    lock_acquired = False
    start = time.monotonic()
    try:
        lock_fh = lock_file.open("w")
        if fcntl is not None:
            while True:
                try:
                    fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                    break
                except BlockingIOError:
                    waited = time.monotonic() - start
                    if waited >= lock_timeout_sec:
                        raise TimeoutError(
                            f"Timed out waiting for session lock {lock_file} after {waited:.1f}s"
                        )
                    logger.debug(
                        f"Session lock busy for {session_name}; waiting ({waited:.1f}s)..."
                    )
                    await asyncio.sleep(lock_poll_sec)
        else:
            # Best-effort fallback: no proper locking, just create file and proceed
            lock_acquired = True
    except Exception as e:
        # If we failed to create/lock, proceed without lock but warn
        logger.warning(f"Could not acquire session lock {lock_file}: {e}")

    try:
        logger.debug(f"Attempting to connect client for session {session_name}")
        await client.connect()

        # Check if already authorized
        if await client.is_user_authorized():
            logger.debug(f"Client already authorized for session {session_name}")
            return client

        # Send code request
        logger.debug(f"Sending code request for phone {phone}")
        send_code_result = await client.send_code_request(phone)

        # Get verification code interactively
        logger.info("Please check your Telegram app and enter the verification code:")
        code = await ask_user("Code: ")
        if code is None:
            raise ValueError("Verification code is required")
        code = code.replace(" ", "").strip()
        if not code:
            raise ValueError("Verification code is required")

        # Try to sign in with code
        try:
            await client.sign_in(
                phone, code, phone_code_hash=send_code_result.phone_code_hash
            )
        except Exception as e:
            if "password" in str(e).lower():
                # 2FA is enabled - check for password in environment
                password = None
                if password_env_key:
                    try:
                        password = find_calmmage_env_key(password_env_key)
                    except ValueError:
                        logger.warning(
                            f"2FA is enabled but {password_env_key} not found in environment"
                        )
                if password is None or not password:
                    # Fallback to generic 2FA password
                    try:
                        password = find_calmmage_env_key(
                            "CALMMAGE_TELEGRAM_2FA_PASSWORD"
                        )
                    except ValueError:
                        password = await ask_user(
                            "Enter 2FA Password or ser it as CALMMAGE_TELEGRAM_2FA_PASSWORD"
                        )
                        if password is None:
                            raise ValueError("2FA password is required")
                        password = password.strip()
                        if not password:
                            raise ValueError("2FA password is required")

                await client.sign_in(password=password)
            else:
                raise

        # Verify authorization was successful
        if await client.is_user_authorized():
            logger.info(f"Successfully authorized client for session {session_name}")
            return client

        raise ValueError(f"Failed to authorize client for session {session_name}")

    except Exception as e:
        logger.error(f"Failed to authenticate client for session {session_name}: {e}")
        # Decide whether to remove the session file: do NOT remove on lock/contention errors
        msg = str(e).lower()
        lock_like = (
            "database is locked" in msg
            or "is in use" in msg
            or "base is in use" in msg
            or isinstance(e, TimeoutError)
        )
        if session_file.exists() and not lock_like:
            logger.debug(f"Removing failed session file {session_file}")
            session_file.unlink()
        else:
            logger.debug(
                f"Not removing session file {session_file} due to lock/timeout condition"
            )
        raise
    finally:
        # Release session lock
        try:
            if lock_acquired and lock_fh is not None and fcntl is not None:
                fcntl.flock(lock_fh.fileno(), fcntl.LOCK_UN)
        finally:
            if lock_fh is not None:
                lock_fh.close()
            # Leave the lock file present for visibility; optional removal is noisy


async def get_telethon_client_primary() -> TelegramClient:
    """
    Get authenticated Telethon client for primary account.

    Automatically discovers credentials from environment variables:
    - CALMMAGE_TELEGRAM_API_ID (shared for both accounts)
    - CALMMAGE_TELEGRAM_API_HASH (shared for both accounts)
    - CALMMAGE_TELEGRAM_PHONE_PRIMARY
    - CALMMAGE_TELEGRAM_2FA_PASSWORD_PRIMARY (optional)

    Session is stored in ~/.calmmage/telethon_sessions/primary.session

    Returns:
        Authenticated TelegramClient for primary account

    Raises:
        ValueError: If required environment variables not found or authentication fails
    """

    # Get shared API credentials
    api_id = find_calmmage_env_key("CALMMAGE_TELEGRAM_API_ID")
    if not api_id:
        raise ValueError(
            "CALMMAGE_TELEGRAM_API_ID not found in environment. "
            "Run the env setup tool to configure Telegram API credentials."
        )

    api_hash = find_calmmage_env_key("CALMMAGE_TELEGRAM_API_HASH")
    if not api_hash:
        raise ValueError(
            "CALMMAGE_TELEGRAM_API_HASH not found in environment. "
            "Run the env setup tool to configure Telegram API credentials."
        )

    phone = find_calmmage_env_key("CALMMAGE_TELEGRAM_PHONE_PRIMARY")
    if not phone:
        raise ValueError(
            "CALMMAGE_TELEGRAM_PHONE_PRIMARY not found in environment. "
            "Run the env setup tool to configure primary Telegram phone number."
        )

    # Use the shared authentication utility
    return await authenticate_telethon_client(
        api_id=int(api_id),
        api_hash=api_hash,
        phone=phone,
        session_name="primary",
        password_env_key="CALMMAGE_TELEGRAM_2FA_PASSWORD_PRIMARY",
    )


async def get_telethon_client_secondary() -> TelegramClient:
    """
    Get authenticated Telethon client for secondary account.

    Automatically discovers credentials from environment variables:
    - CALMMAGE_TELEGRAM_API_ID (shared for both accounts)
    - CALMMAGE_TELEGRAM_API_HASH (shared for both accounts)
    - CALMMAGE_TELEGRAM_PHONE_SECONDARY
    - CALMMAGE_TELEGRAM_2FA_PASSWORD_SECONDARY (optional)

    Session is stored in ~/.calmmage/telethon_sessions/secondary.session

    Returns:
        Authenticated TelegramClient for secondary account

    Raises:
        ValueError: If required environment variables not found or authentication fails
    """
    # Get shared API credentials
    api_id = find_calmmage_env_key("CALMMAGE_TELEGRAM_API_ID")
    if not api_id:
        raise ValueError(
            "CALMMAGE_TELEGRAM_API_ID not found in environment. "
            "Run the env setup tool to configure Telegram API credentials."
        )

    api_hash = find_calmmage_env_key("CALMMAGE_TELEGRAM_API_HASH")
    if not api_hash:
        raise ValueError(
            "CALMMAGE_TELEGRAM_API_HASH not found in environment. "
            "Run the env setup tool to configure Telegram API credentials."
        )

    phone = find_calmmage_env_key("CALMMAGE_TELEGRAM_PHONE_SECONDARY")
    if not phone:
        raise ValueError(
            "CALMMAGE_TELEGRAM_PHONE_SECONDARY not found in environment. "
            "Run the env setup tool to configure secondary Telegram phone number."
        )

    # Use the shared authentication utility
    return await authenticate_telethon_client(
        api_id=int(api_id),
        api_hash=api_hash,
        phone=phone,
        session_name="secondary",
        password_env_key="CALMMAGE_TELEGRAM_2FA_PASSWORD_SECONDARY",
    )


async def get_telethon_client_for_user(
    user_id: int,
    api_id: Optional[int] = None,
    api_hash: Optional[str] = None,
    phone: Optional[str] = None,
    session_dir: Optional[Path] = None,
    password_env_key: Optional[str] = None,
) -> TelegramClient:
    """
    Get authenticated Telethon client for a specific user ID.

    This is useful for telegram_downloader and other tools that need
    to authenticate with custom user IDs.

    Args:
        user_id: Telegram user ID for session naming
        api_id: Telegram API ID (defaults to CALMMAGE_TELEGRAM_API_ID)
        api_hash: Telegram API Hash (defaults to CALMMAGE_TELEGRAM_API_HASH)
        phone: Phone number (defaults to CALMMAGE_TELEGRAM_PHONE_NUMBER)
        session_dir: Directory to store session files (defaults to SESSIONS_DIR)
        password_env_key: Environment variable name for 2FA password

    Returns:
        Authenticated TelegramClient for the user

    Raises:
        ValueError: If required credentials not found or authentication fails
    """
    # Get API credentials with defaults
    if api_id is None:
        api_id = int(find_calmmage_env_key("CALMMAGE_TELEGRAM_API_ID"))
        if not api_id:
            # Fallback to old env var names for backward compatibility
            api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
        if not api_id:
            raise ValueError(
                "CALMMAGE_TELEGRAM_API_ID not found in environment. "
                "Run the env setup tool to configure Telegram API credentials."
            )

    if api_hash is None:
        api_hash = find_calmmage_env_key("CALMMAGE_TELEGRAM_API_HASH")
        if not api_hash:
            # Fallback to old env var names for backward compatibility
            api_hash = os.getenv("TELEGRAM_API_HASH")
        if not api_hash:
            raise ValueError(
                "CALMMAGE_TELEGRAM_API_HASH not found in environment. "
                "Run the env setup tool to configure Telegram API credentials."
            )

    if phone is None:
        phone = find_calmmage_env_key("CALMMAGE_TELEGRAM_PHONE_NUMBER")
        if not phone:
            # Fallback to old env var names for backward compatibility
            phone = find_calmmage_env_key("TELEGRAM_PHONE_NUMBER")
        if not phone:
            raise ValueError(
                "CALMMAGE_TELEGRAM_PHONE_NUMBER not found in environment. "
                "Run the env setup tool to configure Telegram phone number."
            )

    # Use the shared authentication utility
    return await authenticate_telethon_client(
        api_id=api_id,
        api_hash=api_hash,
        phone=phone,
        session_name=f"user_{user_id}",
        session_dir=session_dir,
        password_env_key=password_env_key,
    )


@alru_cache()
async def get_telethon_client(account: str = "primary") -> TelegramClient:
    """
    Get authenticated Telethon client by account name.

    Args:
        account: 'primary' or 'secondary'

    Returns:
        Authenticated TelegramClient for the specified account

    Raises:
        ValueError: If unknown account name or authentication fails
    """
    if account.lower() == "primary":
        return await get_telethon_client_primary()
    elif account.lower() == "secondary":
        return await get_telethon_client_secondary()
    else:
        raise ValueError(f"Unknown account: {account}. Use 'primary' or 'secondary'")


async def main():
    """Example usage of telethon client utilities."""
    from rich.console import Console
    # from rich.table import Table

    console = Console()

    try:
        console.print("\n[cyan]Getting primary Telethon client...[/cyan]")
        client = await get_telethon_client_primary()

        # Get user info
        me = await client.get_me()
        assert isinstance(me, User)
        console.print(
            f"[green]✓ Successfully connected as:[/green] {me.first_name} {me.last_name or ''}"
            f" (@{me.username or 'no username'})"
        )

        # Get a sample dialog
        async for dialog in client.iter_dialogs(limit=1):
            console.print(
                f"[blue]Sample dialog:[/blue] {dialog.name} (ID: {dialog.id})"
            )

        client.disconnect()

    except Exception as e:
        console.print(f"[red]✗ Failed to get primary client:[/red] {e}")

    # Try secondary if configured

    try:
        console.print("\n[cyan]Getting secondary Telethon client...[/cyan]")
        client = await get_telethon_client_secondary()

        # Get user info
        me = await client.get_me()
        assert isinstance(me, User)
        console.print(
            f"[green]✓ Successfully connected as:[/green] {me.first_name} {me.last_name or ''}"
            f" (@{me.username or 'no username'})"
        )

        client.disconnect()

    except Exception as e:
        console.print(f"[red]✗ Failed to get secondary client:[/red] {e}")


if __name__ == "__main__":
    asyncio.run(main())
