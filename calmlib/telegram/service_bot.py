"""
Simple service bot utilities for calmmage ecosystem.

Provides hassle-free access to production and development telegram bots
for automated messaging and user interactions. Tokens are automatically
discovered from environment variables set up by the env setup tool.
"""

from typing import Any, Dict, List, Optional

from aiogram import Bot
from dotenv import load_dotenv

from calmlib.utils.env_discovery import find_calmmage_env_key

# Auto-load environment variables from ~/.env
load_dotenv()


def get_prod_bot(**kwargs: Any) -> Bot:
    """
    Get production service bot instance.

    Automatically discovers bot token from CALMMAGE_SERVICE_BOT_TOKEN_PROD environment variable.

    Args:
        **kwargs: Additional parameters passed to Bot constructor

    Returns:
        aiogram.Bot: Production bot instance ready for use

    Raises:
        ValueError: If production bot token not found in environment
        ImportError: If aiogram is not installed
    """

    token = find_calmmage_env_key("CALMMAGE_SERVICE_BOT_TOKEN_PROD")
    if not token:
        raise ValueError(
            "CALMMAGE_SERVICE_BOT_TOKEN_PROD not found in environment. "
            "Run the env setup tool to configure telegram service bot tokens."
        )

    return Bot(token, **kwargs)


def get_dev_bot(**kwargs: Any) -> Bot:
    """
    Get development/test service bot instance.

    Automatically discovers bot token from CALMMAGE_SERVICE_BOT_TOKEN_DEV environment variable.
    Falls back to production bot if dev token is not configured.

    Args:
        **kwargs: Additional parameters passed to Bot constructor

    Returns:
        aiogram.Bot: Development bot instance ready for use

    Raises:
        ValueError: If neither dev nor prod bot token found in environment
        ImportError: If aiogram is not installed
    """

    token = find_calmmage_env_key("CALMMAGE_SERVICE_BOT_TOKEN_DEV")
    if token:
        return Bot(token, **kwargs)

    # Fallback to production bot for simple setups
    return get_prod_bot(**kwargs)


def get_bot(environment: str = "prod", **kwargs: Any) -> Bot:
    """
    Get service bot by environment name.

    Args:
        environment: 'prod' for production, 'dev' for development
        **kwargs: Additional parameters passed to Bot constructor

    Returns:
        aiogram.Bot: Bot instance for the specified environment
    """
    if environment.lower() in ["prod", "production"]:
        return get_prod_bot(**kwargs)
    elif environment.lower() in ["dev", "development", "test"]:
        return get_dev_bot(**kwargs)
    else:
        raise ValueError(f"Unknown environment: {environment}. Use 'prod' or 'dev'")


# todo: grab/reuse botspot.send_safe and other utils
async def send_message(chat_id: int, text: str, bot: Bot, **kwargs: Any) -> Any:
    """
    Send a message using service bot.

    Args:
        chat_id: Telegram chat ID to send message to
        text: Message text to send
        bot: Bot instance to use (get_prod_bot() or get_dev_bot())
        **kwargs: Additional parameters passed to bot.send_message()

    Returns:
        Message: Sent message object
    """
    try:
        from botspot import send_safe
        from botspot.core.bot_manager import BotManager

        bm = BotManager()
        return await send_safe(chat_id, text, bm.deps, **kwargs)
    except ImportError:
        pass

    return await bot.send_message(chat_id, text, **kwargs)


async def get_updates(
    bot: Bot, offset: Optional[int] = None, limit: int = 100
) -> List[Any]:
    """
    Get updates from telegram bot (simple polling).

    Args:
        bot: Bot instance to use (get_prod_bot() or get_dev_bot())
        offset: Offset for getting updates
        limit: Maximum number of updates to fetch

    Returns:
        List of Update objects
    """
    return await bot.get_updates(offset=offset, limit=limit)


def check_bot_tokens() -> Dict[str, bool]:
    """
    Check which bot tokens are configured in environment.

    Returns:
        Dict with keys 'prod' and 'dev' indicating token availability
    """
    return {
        "prod": bool(find_calmmage_env_key("CALMMAGE_SERVICE_BOT_TOKEN_PROD")),
        "dev": bool(find_calmmage_env_key("CALMMAGE_SERVICE_BOT_TOKEN_DEV")),
    }
