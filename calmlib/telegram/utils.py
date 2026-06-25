from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from calmlib.telegram.telethon_client import get_telethon_client_context

from .models import (
    TelegramChannel,
    TelegramChat,
    TelegramFolder,
    TelegramGroupChat,
    TelegramUserChat,
)

if TYPE_CHECKING:
    from telethon import TelegramClient
    from telethon.types import (
        Dialog,
        InputPeerChannel,
        InputPeerChannelFromMessage,
        InputPeerChat,
        InputPeerEmpty,
        InputPeerSelf,
        InputPeerUser,
    )

    InputPeer = Union[  # noqa: UP007
        InputPeerUser,
        InputPeerChannel,
        InputPeerChannelFromMessage,
        InputPeerChat,
        InputPeerSelf,
        InputPeerEmpty,
    ]

    from calmlib.telegram.telegram_cache import TelegramCache


async def get_chat_id(
    username: str, telethon_client: Optional["TelegramClient"] = None
) -> int:
    async def _resolve(client: "TelegramClient") -> int:
        user = await client.get_input_entity(username)
        if isinstance(user, InputPeerUser):
            return user.user_id
        elif isinstance(user, InputPeerChannel):
            return user.channel_id
        elif isinstance(user, InputPeerChat):
            return user.chat_id
        elif isinstance(user, InputPeerSelf):
            try:
                return user.user_id
            except AttributeError:
                raise ValueError(
                    f"InputPeerSelf for {username} does not have a user_id"
                )
        elif isinstance(user, InputPeerEmpty):
            raise ValueError(f"InputPeerEmpty for {username}")
        else:
            raise ValueError(f"Unknown input peer type for {username} - {type(user)}")

    if telethon_client is None:
        async with get_telethon_client_context() as client:
            return await _resolve(client)
    return await _resolve(telethon_client)


def get_telegram_cache(
    root_path: Path | None = None,
    telethon_account: str = "secondary",
    mongo_conn_str: str | None = None,
    db_name: str | None = None,
    mongo_enabled: bool | None = None,
) -> "TelegramCache":
    from calmlib.telegram.telegram_cache import TelegramCache

    cache = TelegramCache(
        root_path=root_path,
        telethon_account=telethon_account,
        mongo_conn_str=mongo_conn_str,
        db_name=db_name,
        mongo_enabled=mongo_enabled,
    )
    if cache.telethon_account != telethon_account:
        raise RuntimeError(
            "TelegramCache singleton already initialized with account "
            f"{cache.telethon_account!r}; requested {telethon_account!r}. "
            "Use separate process or context-managed cache for another account."
        )
    return cache


async def get_raw_messages(source: str, **kwargs):
    """
    source: username of chat_id
    """
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_raw_messages(source, **kwargs)


async def get_raw_dialogs() -> list["Dialog"]:
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_raw_dialogs()


async def get_chats(**kwargs) -> list[TelegramChat]:
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_chats(**kwargs)


async def get_group_chats(**kwargs) -> list[TelegramGroupChat]:
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_group_chats(**kwargs)


async def get_participants(chat_id: int | str, **kwargs):
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_participants(chat_id, **kwargs)


async def get_participants_for_chats(chat_ids: list[int | str], **kwargs):
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_participants_for_chats(chat_ids, **kwargs)


async def get_channels(**kwargs) -> list[TelegramChannel]:
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_channels(**kwargs)


async def get_users_chats(**kwargs) -> list[TelegramUserChat]:
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_users(**kwargs)


async def get_folders(**kwargs) -> list[TelegramFolder]:
    telegram_cache = get_telegram_cache()
    return await telegram_cache.get_folders(**kwargs)
