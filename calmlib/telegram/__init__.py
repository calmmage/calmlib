"""One library for local Telegram: cache, accounts, folders, archive, bots.

Where things live on this machine: ``config.py`` (one TOML file). What is there: ``tgl status``.
The aiogram side (service bot, bot tester) loads on first use, so ``import calmlib.telegram``
stays fast for scripts that only read the cache.
"""

from importlib import import_module

from .chat_utils import (
    chat_is_bot,
    chat_is_broadcast,
    chat_is_channel,
    chat_is_group,
    chat_is_in_folder,
    chat_is_private,
    get_chat_type,
)
from .models import (
    TelegramBotChat,
    TelegramChannel,
    TelegramChat,
    TelegramFolder,
    TelegramGroupChat,
    TelegramMessage,
    TelegramUserChat,
)
from .bot_inventory import (
    BotActivity,
    InventoryResult,
    OwnedBot,
    collect_inventory,
    find_bot_dialogs,
    list_owned_bots,
    scan_bot_activity,
)
from .config import AccountMismatch, AccountNotBound, TelegramConfig, get_config
from .telethon_client import (
    get_telethon_client,
    get_telethon_client_context,
    get_telethon_client_primary,
    get_telethon_client_secondary,
    get_telethon_client_service,
)
from .telegram_cache import TelegramCache
from .utils import (
    get_channels,
    get_chat_id,
    get_chats,
    get_folders,
    get_group_chats,
    get_participants,
    get_participants_for_chats,
    get_raw_dialogs,
    get_raw_messages,
    get_telegram_cache,
    get_users_chats,
)

_LAZY = {
    "check_bot_tokens": "service_bot",
    "get_bot": "service_bot",
    "get_dev_bot": "service_bot",
    "get_prod_bot": "service_bot",
    "get_updates": "service_bot",
    "send_message": "service_bot",
    "BotTester": "bot_tester",
}


def __getattr__(name):
    if name in _LAZY:
        value = getattr(import_module(f".{_LAZY[name]}", __name__), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "get_prod_bot",
    "get_dev_bot",
    "get_bot",
    "send_message",
    "get_updates",
    "check_bot_tokens",
    # cache and where it lives
    "TelegramCache",
    "TelegramConfig",
    "get_config",
    "AccountNotBound",
    "AccountMismatch",
    # models
    "TelegramChat",
    "TelegramGroupChat",
    "TelegramUserChat",
    "TelegramBotChat",
    "TelegramChannel",
    "TelegramMessage",
    "TelegramFolder",
    # utils
    "get_telegram_cache",
    "get_chats",
    "get_chat_id",
    "get_group_chats",
    "get_participants",
    "get_participants_for_chats",
    "get_users_chats",
    "get_folders",
    "get_channels",
    "get_raw_dialogs",
    "get_raw_messages",
    # chat utils
    "chat_is_bot",
    "chat_is_channel",
    "chat_is_private",
    "chat_is_group",
    "chat_is_broadcast",
    "chat_is_in_folder",
    "get_chat_type",
    # bot tester
    "BotTester",
    # bot inventory
    "BotActivity",
    "InventoryResult",
    "OwnedBot",
    "collect_inventory",
    "find_bot_dialogs",
    "list_owned_bots",
    "scan_bot_activity",
    # telethon client
    "get_telethon_client",
    "get_telethon_client_context",
    "get_telethon_client_primary",
    "get_telethon_client_secondary",
    "get_telethon_client_service",
]
