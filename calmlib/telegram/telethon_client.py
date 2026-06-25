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

from async_lru import alru_cache
from loguru import logger
from telethon import TelegramClient
from telethon.types import User

from calmlib.utils.env_discovery import find_calmmage_env_key
from calmlib.utils.user_interactions import ask_user, notify_user

try:
    import fcntl  # POSIX file locking
except Exception:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore

# Session storage location - using ~/.calmmage/telethon_sessions
SESSIONS_DIR = Path.home() / ".calmmage" / "telethon_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_LOCK_RETRY_ATTEMPTS = 10
DATABASE_LOCK_BACKOFF_BASE_SEC = 1.5
DATABASE_LOCK_BACKOFF_MAX_SEC = 150.0


def _is_database_locked_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "database is locked" in message
        or "operationalerror: database is locked" in message
    )


def _should_remove_session_file_after_auth_failure(
    exc: Exception, session_file_existed_before_auth: bool
) -> bool:
    """Return whether a failed auth attempt should remove the session file."""
    if session_file_existed_before_auth:
        return False

    msg = str(exc).lower()
    lock_like = (
        "database is locked" in msg
        or "is in use" in msg
        or "base is in use" in msg
        or isinstance(exc, TimeoutError)
    )
    return not lock_like


def _describe_sent_code(send_code_result) -> str:
    code_type = type(getattr(send_code_result, "type", None)).__name__
    next_type = type(getattr(send_code_result, "next_type", None)).__name__
    timeout = getattr(send_code_result, "timeout", None)
    return f"type={code_type}, next_type={next_type}, timeout={timeout}"


def _sent_code_prompt(send_code_result) -> str:
    code_type = type(getattr(send_code_result, "type", None)).__name__
    next_type = type(getattr(send_code_result, "next_type", None)).__name__
    timeout = getattr(send_code_result, "timeout", None)

    delivery = {
        "SentCodeTypeApp": "Telegram app",
        "SentCodeTypeSms": "SMS",
        "SentCodeTypeFirebaseSms": "SMS",
        "SentCodeTypeFragmentSms": "Fragment SMS",
        "SentCodeTypeSmsPhrase": "SMS phrase",
        "SentCodeTypeSmsWord": "SMS word",
        "SentCodeTypeCall": "phone call",
        "SentCodeTypeFlashCall": "flash call",
        "SentCodeTypeMissedCall": "missed call",
        "SentCodeTypeEmailCode": "email",
    }.get(code_type, code_type)

    parts = [f"delivery: {delivery}"]
    if next_type != "NoneType":
        next_delivery = {
            "CodeTypeSms": "SMS",
            "CodeTypeCall": "phone call",
            "CodeTypeFlashCall": "flash call",
            "CodeTypeMissedCall": "missed call",
            "CodeTypeFragmentSms": "Fragment SMS",
        }.get(next_type, next_type)
        parts.append(f"next: {next_delivery}")
    if timeout is not None:
        parts.append(f"timeout: {timeout}s")

    return f"Code ({', '.join(parts)})"


def _sent_code_wait_timeout(send_code_result, default_timeout: float = 1200.0) -> float:
    """Wait long enough for Telegram's next delivery method to become available."""
    if getattr(send_code_result, "next_type", None) is None:
        return default_timeout

    timeout = getattr(send_code_result, "timeout", None)
    if not isinstance(timeout, int | float):
        return default_timeout

    return min(default_timeout, max(300.0, timeout + 180.0))


async def authenticate_telethon_client(
    api_id: int,
    api_hash: str,
    phone: str,
    session_name: str,
    session_dir: Path | None = None,
    password_env_key: str | None = None,
    lock_timeout_sec: float = 1500.0,
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
    retry_attempts = DATABASE_LOCK_RETRY_ATTEMPTS

    for attempt in range(retry_attempts):
        try:
            return await _authenticate_telethon_client_once(
                api_id=api_id,
                api_hash=api_hash,
                phone=phone,
                session_name=session_name,
                session_dir=session_dir,
                password_env_key=password_env_key,
                lock_timeout_sec=lock_timeout_sec,
                lock_poll_sec=lock_poll_sec,
            )
        except Exception as exc:
            should_retry = attempt < retry_attempts - 1 and _is_database_locked_error(
                exc
            )
            if not should_retry:
                raise

            wait = min(
                DATABASE_LOCK_BACKOFF_MAX_SEC,
                DATABASE_LOCK_BACKOFF_BASE_SEC * (2**attempt),
            )
            logger.warning(
                f"Session {session_name} database locked (attempt {attempt + 1}"
                f"/{retry_attempts}); retrying in {wait:.1f}s"
            )
            await asyncio.sleep(wait)
    raise RuntimeError(
        f"Failed to authenticate session {session_name} after {retry_attempts} attempts"
    )


async def _authenticate_telethon_client_once(
    api_id: int,
    api_hash: str,
    phone: str,
    session_name: str,
    session_dir: Path | None = None,
    password_env_key: str | None = None,
    lock_timeout_sec: float = 1500.0,
    lock_poll_sec: float = 0.5,
) -> TelegramClient:
    logger.debug(
        f"_authenticate_telethon_client_once() called for session '{session_name}'"
    )

    if session_dir is None:
        session_dir = SESSIONS_DIR

    session_path = session_dir / session_name
    session_file = session_path.with_suffix(".session")
    session_file_existed_before_auth = session_file.exists()

    logger.debug(f"Creating TelegramClient with session path: {session_path}")
    client = TelegramClient(str(session_path), api_id, api_hash)
    logger.debug(f"TelegramClient object created for session '{session_name}'")

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
        if isinstance(e, TimeoutError):
            raise
        # If we failed to create/lock for an unexpected reason, proceed without
        # the advisory lock but warn.
        logger.warning(f"Could not acquire session lock {lock_file}: {e}")

    try:
        logger.debug(f"Calling client.connect() for session '{session_name}'")
        await client.connect()
        logger.debug(f"Client connected successfully for session '{session_name}'")

        # Check if already authorized
        logger.debug(f"Checking if user is authorized for session '{session_name}'")
        if await client.is_user_authorized():
            logger.debug(
                f"Client already authorized for session '{session_name}', skipping auth flow"
            )
            return client

        logger.debug(
            f"User not authorized for session '{session_name}', starting auth flow"
        )

        # Send code request
        logger.debug(f"Sending code request for phone {phone}")
        send_code_result = await client.send_code_request(phone)
        logger.info(
            "Telegram sent login code metadata for session "
            f"{session_name}: {_describe_sent_code(send_code_result)}"
        )

        # Get verification code interactively
        logger.info("Please check your Telegram app and enter the verification code:")
        code = await ask_user(
            _sent_code_prompt(send_code_result),
            timeout=_sent_code_wait_timeout(send_code_result),
        )
        if code is None and getattr(send_code_result, "next_type", None) is not None:
            logger.info(
                "No login code received for session "
                f"{session_name}; requesting next Telegram delivery method"
            )
            await notify_user("No code received. Requesting next delivery method.")
            send_code_result = await client.send_code_request(phone)
            logger.info(
                "Telegram resent login code metadata for session "
                f"{session_name}: {_describe_sent_code(send_code_result)}"
            )
            code = await ask_user(
                _sent_code_prompt(send_code_result),
                timeout=_sent_code_wait_timeout(send_code_result),
            )
        if code is None:
            await notify_user("Didn't receive code. Exiting.")
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
                            "Enter 2FA Password or set it as CALMMAGE_TELEGRAM_2FA_PASSWORD",
                            timeout=180.0,
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
            await notify_user("Connected successfully")
            return client

        raise ValueError(f"Failed to authorize client for session {session_name}")

    except Exception as e:
        logger.error(f"Failed to authenticate client for session {session_name}: {e}")
        # Only remove files created by this failed auth attempt. A transient
        # prompt timeout or network issue must not destroy a reusable session.
        should_remove_session_file = _should_remove_session_file_after_auth_failure(
            e, session_file_existed_before_auth
        )
        if session_file.exists() and should_remove_session_file:
            logger.debug(f"Removing failed session file {session_file}")
            session_file.unlink()
        else:
            logger.debug(
                f"Not removing session file {session_file}; "
                f"preexisting={session_file_existed_before_auth}, "
                f"should_remove={should_remove_session_file}"
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
    logger.debug("get_telethon_client_primary() called")

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

    logger.debug(f"Authenticating primary account with phone {phone}")
    # Use the shared authentication utility
    client = await authenticate_telethon_client(
        api_id=int(api_id),
        api_hash=api_hash,
        phone=phone,
        session_name="primary",
        password_env_key="CALMMAGE_TELEGRAM_2FA_PASSWORD_PRIMARY",
    )
    logger.debug("Primary client authenticated successfully")
    return client


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


async def get_telethon_client_service() -> TelegramClient:
    """
    Get authenticated Telethon client for service account.

    Dedicated phone number for automation — safe for writes, channel monitoring,
    and actions that shouldn't pollute the personal account.

    Env vars:
    - CALMMAGE_TELEGRAM_API_ID (shared)
    - CALMMAGE_TELEGRAM_API_HASH (shared)
    - CALMMAGE_TELEGRAM_PHONE_SERVICE
    - CALMMAGE_TELEGRAM_2FA_PASSWORD_SERVICE (optional)

    Session: ~/.calmmage/telethon_sessions/service.session
    """
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

    phone = find_calmmage_env_key("CALMMAGE_TELEGRAM_PHONE_SERVICE")
    if not phone:
        raise ValueError(
            "CALMMAGE_TELEGRAM_PHONE_SERVICE not found in environment. "
            "Run the env setup tool to configure service Telegram phone number."
        )

    return await authenticate_telethon_client(
        api_id=int(api_id),
        api_hash=api_hash,
        phone=phone,
        session_name="service",
        password_env_key="CALMMAGE_TELEGRAM_2FA_PASSWORD_SERVICE",
    )


async def get_telethon_client_for_user(
    user_id: int,
    api_id: int | None = None,
    api_hash: str | None = None,
    phone: str | None = None,
    session_dir: Path | None = None,
    password_env_key: str | None = None,
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
        account: 'primary', 'secondary', or 'service'
    """
    if account.lower() == "primary":
        return await get_telethon_client_primary()
    elif account.lower() == "secondary":
        return await get_telethon_client_secondary()
    elif account.lower() == "service":
        return await get_telethon_client_service()
    else:
        raise ValueError(
            f"Unknown account: {account}. Use 'primary', 'secondary', or 'service'"
        )


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


DEFAULT_IDLE_DISCONNECT_SEC = 300


class TelethonClientLeaseManager:
    """Tracks Telethon client leases and disconnects after idle timeout."""

    def __init__(self, account: str, idle_timeout: float = DEFAULT_IDLE_DISCONNECT_SEC):
        self.account = account
        self.idle_timeout = idle_timeout
        self._client: TelegramClient | None = None
        self._active_leases = 0
        self._idle_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def acquire(self) -> TelegramClient:
        async with self._lock:
            client = await get_telethon_client(self.account)
            self._client = client
            if not client.is_connected():
                await client.connect()
            self._active_leases += 1
            self._cancel_idle_task()
            return client

    async def release(self) -> None:
        async with self._lock:
            if self._active_leases <= 0:
                logger.warning(
                    f"Tried to release Telethon client lease for {self.account} with no active leases"
                )
                return
            self._active_leases -= 1
            if self._active_leases == 0:
                self._schedule_idle_disconnect()

    def _cancel_idle_task(self) -> None:
        if self._idle_task is not None:
            self._idle_task.cancel()
            self._idle_task = None

    def _schedule_idle_disconnect(self) -> None:
        if self._idle_task is not None:
            self._idle_task.cancel()
        loop = asyncio.get_running_loop()
        self._idle_task = loop.create_task(self._idle_disconnect_after_idle())

    async def _idle_disconnect_after_idle(self) -> None:
        try:
            await asyncio.sleep(self.idle_timeout)
            async with self._lock:
                if (
                    self._active_leases == 0
                    and self._client
                    and self._client.is_connected()
                ):
                    logger.debug(
                        f"Auto-disconnecting idle Telethon client for account {self.account}"
                    )
                    await self._client.disconnect()
        except asyncio.CancelledError:
            return
        finally:
            self._idle_task = None


_lease_managers: dict[str, TelethonClientLeaseManager] = {}


def _get_lease_manager(
    account: str, idle_timeout: float | None = None
) -> TelethonClientLeaseManager:
    manager = _lease_managers.get(account)
    if manager is None or (
        idle_timeout is not None and manager.idle_timeout != idle_timeout
    ):
        timeout = (
            idle_timeout if idle_timeout is not None else DEFAULT_IDLE_DISCONNECT_SEC
        )
        manager = TelethonClientLeaseManager(account=account, idle_timeout=timeout)
        _lease_managers[account] = manager
    return manager


class TelethonClientContext:
    """
    Context manager for telethon clients that ensures proper cleanup.

    Usage:
        async with get_telethon_client_context("secondary") as client:
            me = await client.get_me()
            # Client disconnects automatically after idle timeout once no contexts are active
    """

    def __init__(self, account: str = "primary", idle_timeout: float | None = None):
        self.account = account
        self._manager = _get_lease_manager(account, idle_timeout)
        self._lease_acquired = False
        self.client: TelegramClient | None = None

    async def __aenter__(self) -> TelegramClient:
        """Connect (if needed) and return the client."""
        self.client = await self._manager.acquire()
        self._lease_acquired = True
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release the lease; disconnect happens after idle timeout."""
        if self._lease_acquired:
            await self._manager.release()
        self._lease_acquired = False
        self.client = None
        return False  # Don't suppress exceptions


def get_telethon_client_context(
    account: str = "primary", idle_timeout: float | None = None
) -> TelethonClientContext:
    """
    Get a context manager for a telethon client.

    This is the recommended way to use telethon clients when you want to ensure
    proper cleanup of connections. The client will be automatically disconnected
    when exiting the context.

    Args:
        account: 'primary' or 'secondary'

    Returns:
        Context manager that yields an authenticated TelegramClient

    Example:
        async with get_telethon_client_context("secondary") as client:
            me = await client.get_me()
            dialogs = await client.get_dialogs()
    """
    return TelethonClientContext(account, idle_timeout=idle_timeout)


if __name__ == "__main__":
    asyncio.run(main())
