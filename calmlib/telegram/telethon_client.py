"""
Simple telethon client utilities for calmmage ecosystem.

Provides hassle-free access to authenticated Telethon clients for
primary and secondary Telegram accounts. Session files are stored
in a stable location and authentication is handled interactively when needed.
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from telethon import TelegramClient
from loguru import logger
from calmlib.utils.env_discovery import load_global_env

# Auto-load environment variables from ~/.env
# load_dotenv()

# Session storage location - using ~/.calmmage/telethon_sessions
SESSIONS_DIR = Path.home() / ".calmmage" / "telethon_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


async def authenticate_telethon_client(
    api_id: int,
    api_hash: str,
    phone: str,
    session_name: str,
    session_dir: Path = None,
    password_env_key: str = None
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
        logger.info(f"Please check your Telegram app and enter the verification code:")
        code = input("Code: ").strip()
        if not code:
            raise ValueError("Verification code is required")
        
        # Try to sign in with code
        try:
            await client.sign_in(phone, code, phone_code_hash=send_code_result.phone_code_hash)
        except Exception as e:
            if "password" in str(e).lower():
                # 2FA is enabled - check for password in environment
                password = None
                if password_env_key:
                    password = os.getenv(password_env_key)
                    if not password:
                        logger.warning(f"2FA is enabled but {password_env_key} not found in environment")
                if not password:
                    # Fallback to generic 2FA password
                    password = os.getenv("CALMMAGE_TELEGRAM_2FA_PASSWORD")
                    if not password:
                        password = input("Enter 2FA Password or ser it as CALMMAGE_TELEGRAM_2FA_PASSWORD").strip()
                        # raise ValueError(
                        #     f"2FA is enabled but password not provided. "
                        #     f"Set {password_env_key or 'CALMMAGE_TELEGRAM_2FA_PASSWORD'} in your ~/.env file."
                        # )
                
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
        # Clean up failed session
        if session_file.exists():
            logger.debug(f"Removing failed session file {session_file}")
            session_file.unlink()
        raise


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
    load_global_env()
    # Get shared API credentials
    api_id = os.getenv('CALMMAGE_TELEGRAM_API_ID')
    if not api_id:
        raise ValueError(
            "CALMMAGE_TELEGRAM_API_ID not found in environment. "
            "Run the env setup tool to configure Telegram API credentials."
        )
    
    api_hash = os.getenv('CALMMAGE_TELEGRAM_API_HASH')
    if not api_hash:
        raise ValueError(
            "CALMMAGE_TELEGRAM_API_HASH not found in environment. "
            "Run the env setup tool to configure Telegram API credentials."
        )
    
    phone = os.getenv('CALMMAGE_TELEGRAM_PHONE_PRIMARY')
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
        password_env_key="CALMMAGE_TELEGRAM_2FA_PASSWORD_PRIMARY"
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
    load_global_env()
    api_id = os.getenv('CALMMAGE_TELEGRAM_API_ID')
    if not api_id:
        raise ValueError(
            "CALMMAGE_TELEGRAM_API_ID not found in environment. "
            "Run the env setup tool to configure Telegram API credentials."
        )
    
    api_hash = os.getenv('CALMMAGE_TELEGRAM_API_HASH')
    if not api_hash:
        raise ValueError(
            "CALMMAGE_TELEGRAM_API_HASH not found in environment. "
            "Run the env setup tool to configure Telegram API credentials."
        )
    
    phone = os.getenv('CALMMAGE_TELEGRAM_PHONE_SECONDARY')
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
        password_env_key="CALMMAGE_TELEGRAM_2FA_PASSWORD_SECONDARY"
    )


async def get_telethon_client_for_user(
    user_id: int,
    api_id: int = None,
    api_hash: str = None,
    phone: str = None,
    session_dir: Path = None,
    password_env_key: str = None) -> TelegramClient:
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
        api_id = os.getenv('CALMMAGE_TELEGRAM_API_ID')
        if not api_id:
            # Fallback to old env var names for backward compatibility
            api_id = os.getenv('TELEGRAM_API_ID')
        if not api_id:
            raise ValueError(
                "CALMMAGE_TELEGRAM_API_ID not found in environment. "
                "Run the env setup tool to configure Telegram API credentials."
            )
        api_id = int(api_id)
    
    if api_hash is None:
        api_hash = os.getenv('CALMMAGE_TELEGRAM_API_HASH')
        if not api_hash:
            # Fallback to old env var names for backward compatibility
            api_hash = os.getenv('TELEGRAM_API_HASH')
        if not api_hash:
            raise ValueError(
                "CALMMAGE_TELEGRAM_API_HASH not found in environment. "
                "Run the env setup tool to configure Telegram API credentials."
            )
    
    if phone is None:
        phone = os.getenv('CALMMAGE_TELEGRAM_PHONE_NUMBER')
        if not phone:
            # Fallback to old env var names for backward compatibility
            phone = os.getenv('TELEGRAM_PHONE_NUMBER')
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
        password_env_key=password_env_key
    )


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


def check_telethon_credentials() -> dict:
    """
    Check which Telethon credentials are configured in environment.
    
    Returns:
        Dict with account availability and credential status
    """
    load_global_env()
    return {
        'api_credentials': {
            'api_id': bool(os.getenv('CALMMAGE_TELEGRAM_API_ID')),
            'api_hash': bool(os.getenv('CALMMAGE_TELEGRAM_API_HASH')),
        },
        'primary': {
            'phone': bool(os.getenv('CALMMAGE_TELEGRAM_PHONE_PRIMARY')),
            '2fa_password': bool(os.getenv('CALMMAGE_TELEGRAM_2FA_PASSWORD_PRIMARY')),
            'session_exists': (SESSIONS_DIR / "primary.session").exists()
        },
        'secondary': {
            'phone': bool(os.getenv('CALMMAGE_TELEGRAM_PHONE_SECONDARY')),
            '2fa_password': bool(os.getenv('CALMMAGE_TELEGRAM_2FA_PASSWORD_SECONDARY')),
            'session_exists': (SESSIONS_DIR / "secondary.session").exists()
        }
    }


async def main():
    """Example usage of telethon client utilities."""
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    # Check credentials
    creds = check_telethon_credentials()
    
    # Display credentials status
    table = Table(title="Telethon Credentials Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    # API credentials (shared)
    table.add_row("API Credentials", "")
    table.add_row("  API ID", "✓" if creds['api_credentials']['api_id'] else "✗")
    table.add_row("  API Hash", "✓" if creds['api_credentials']['api_hash'] else "✗")
    
    # Primary account
    table.add_row("Primary Account", "")
    table.add_row("  Phone", "✓" if creds['primary']['phone'] else "✗")
    table.add_row("  2FA Password", "✓" if creds['primary']['2fa_password'] else "✗")
    table.add_row("  Session Exists", "✓" if creds['primary']['session_exists'] else "✗")
    
    # Secondary account
    table.add_row("Secondary Account", "")
    table.add_row("  Phone", "✓" if creds['secondary']['phone'] else "✗")
    table.add_row("  2FA Password", "✓" if creds['secondary']['2fa_password'] else "✗")
    table.add_row("  Session Exists", "✓" if creds['secondary']['session_exists'] else "✗")
    
    console.print(table)
    
    # Try to get primary client
    if creds['api_credentials']['api_id'] and creds['primary']['phone']:
        try:
            console.print("\n[cyan]Getting primary Telethon client...[/cyan]")
            client = await get_telethon_client_primary()
            
            # Get user info
            me = await client.get_me()
            console.print(
                f"[green]✓ Successfully connected as:[/green] {me.first_name} {me.last_name or ''}"
                f" (@{me.username or 'no username'})"
            )
            
            # Get a sample dialog
            async for dialog in client.iter_dialogs(limit=1):
                console.print(f"[blue]Sample dialog:[/blue] {dialog.name} (ID: {dialog.id})")
            
            await client.disconnect()
            
        except Exception as e:
            console.print(f"[red]✗ Failed to get primary client:[/red] {e}")
    
    # Try secondary if configured
    if creds['api_credentials']['api_id'] and creds['secondary']['phone']:
        try:
            console.print("\n[cyan]Getting secondary Telethon client...[/cyan]")
            client = await get_telethon_client_secondary()
            
            # Get user info
            me = await client.get_me()
            console.print(f"[green]✓ Successfully connected as:[/green] {me.first_name} {me.last_name or ''}"
                          f" (@{me.username or 'no username'})")
            
            await client.disconnect()
            
        except Exception as e:
            console.print(f"[red]✗ Failed to get secondary client:[/red] {e}")


if __name__ == "__main__":
    asyncio.run(main())