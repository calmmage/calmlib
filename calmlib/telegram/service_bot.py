"""
Simple service bot utilities for calmmage ecosystem.

Provides hassle-free access to production and development telegram bots
for automated messaging and user interactions. Tokens are automatically 
discovered from environment variables set up by the env setup tool.
"""

import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Auto-load environment variables from ~/.env
load_dotenv()


def get_prod_bot():
    """
    Get production service bot instance.
    
    Automatically discovers bot token from CALMMAGE_SERVICE_BOT_TOKEN_PROD environment variable.
    
    Returns:
        aiogram.Bot: Production bot instance ready for use
        
    Raises:
        ValueError: If production bot token not found in environment
        ImportError: If aiogram is not installed
    """
    try:
        from aiogram import Bot
    except ImportError:
        raise ImportError("aiogram is required for service bot functionality. Run: poetry install")
    
    token = os.getenv('CALMMAGE_SERVICE_BOT_TOKEN_PROD')
    if not token:
        raise ValueError(
            "CALMMAGE_SERVICE_BOT_TOKEN_PROD not found in environment. "
            "Run the env setup tool to configure telegram service bot tokens."
        )
    
    return Bot(token)


def get_dev_bot():
    """
    Get development/test service bot instance.
    
    Automatically discovers bot token from CALMMAGE_SERVICE_BOT_TOKEN_DEV environment variable.
    Falls back to production bot if dev token is not configured.
    
    Returns:
        aiogram.Bot: Development bot instance ready for use
        
    Raises:
        ValueError: If neither dev nor prod bot token found in environment
        ImportError: If aiogram is not installed
    """
    try:
        from aiogram import Bot
    except ImportError:
        raise ImportError("aiogram is required for service bot functionality. Run: poetry install")
    
    token = os.getenv('CALMMAGE_SERVICE_BOT_TOKEN_DEV')
    if token:
        return Bot(token)
    
    # Fallback to production bot for simple setups
    return get_prod_bot()


def get_bot(environment: str = 'prod'):
    """
    Get service bot by environment name.
    
    Args:
        environment: 'prod' for production, 'dev' for development
        
    Returns:
        aiogram.Bot: Bot instance for the specified environment
    """
    if environment.lower() in ['prod', 'production']:
        return get_prod_bot()
    elif environment.lower() in ['dev', 'development', 'test']:
        return get_dev_bot()
    else:
        raise ValueError(f"Unknown environment: {environment}. Use 'prod' or 'dev'")


async def send_message(chat_id: int, text: str, bot, **kwargs) -> Any:
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
    return await bot.send_message(chat_id, text, **kwargs)


async def get_updates(bot, offset: Optional[int] = None, limit: int = 100) -> List[Any]:
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
        'prod': bool(os.getenv('CALMMAGE_SERVICE_BOT_TOKEN_PROD')),
        'dev': bool(os.getenv('CALMMAGE_SERVICE_BOT_TOKEN_DEV'))
    }