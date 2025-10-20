from pathlib import Path
from typing import TYPE_CHECKING, Union

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

from calmlib.telegram.telethon_client import get_telethon_client

from .models import (
    TelegramChannel,
    TelegramChat,
    TelegramFolder,
    TelegramGroupChat,
    TelegramUserChat,
)

InputPeer = Union[
    InputPeerUser,
    InputPeerChannel,
    InputPeerChannelFromMessage,
    InputPeerChat,
    InputPeerSelf,
    InputPeerEmpty,
]

if TYPE_CHECKING:
    from calmlib.telegram.telegram_cache import TelegramCache


async def get_chat_id(
    username: str, telethon_client: TelegramClient | None = None
) -> int:
    if telethon_client is None:
        telethon_client = await get_telethon_client()
    user = await telethon_client.get_input_entity(username)
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
            raise ValueError(f"InputPeerSelf for {username} does not have a user_id")
    elif isinstance(user, InputPeerEmpty):
        raise ValueError(f"InputPeerEmpty for {username}")
    else:
        raise ValueError(f"Unknown input peer type for {username} - {type(user)}")


def get_telegram_cache(
    root_path: Path | None = None,
    telethon_client: TelegramClient | None = None,
    telethon_account: str = "secondary",
    mongo_conn_str: str | None = None,
    db_name: str | None = None,
    mongo_enabled: bool | None = None,
) -> "TelegramCache":
    from calmlib.telegram.telegram_cache import TelegramCache

    return TelegramCache(
        root_path=root_path,
        telethon_client=telethon_client,
        telethon_account=telethon_account,
        mongo_conn_str=mongo_conn_str,
        db_name=db_name,
        mongo_enabled=mongo_enabled,
    )


async def get_raw_messages(
    source: str, telethon_client: TelegramClient | None = None, **kwargs
):
    """
    source: username of chat_id
    """

    telegram_cache = get_telegram_cache(telethon_client=telethon_client)
    return await telegram_cache.get_raw_messages(source, **kwargs)


async def get_raw_dialogs(
    telethon_client: TelegramClient | None = None,
) -> list[Dialog]:
    telegram_cache = get_telegram_cache(telethon_client=telethon_client)
    return await telegram_cache.get_raw_dialogs()


async def get_chats(
    telethon_client: TelegramClient | None = None, **kwargs
) -> list[TelegramChat]:
    telegram_cache = get_telegram_cache(telethon_client=telethon_client)
    return await telegram_cache.get_chats(**kwargs)


async def get_group_chats(
    telethon_client: TelegramClient | None = None, **kwargs
) -> list[TelegramGroupChat]:
    telegram_cache = get_telegram_cache(telethon_client=telethon_client)
    return await telegram_cache.get_group_chats(**kwargs)


async def get_channels(
    telethon_client: TelegramClient | None = None, **kwargs
) -> list[TelegramChannel]:
    telegram_cache = get_telegram_cache(telethon_client=telethon_client)
    return await telegram_cache.get_channels(**kwargs)


async def get_users_chats(
    telethon_client: TelegramClient | None = None, **kwargs
) -> list[TelegramUserChat]:
    telegram_cache = get_telegram_cache(telethon_client=telethon_client)
    return await telegram_cache.get_users(**kwargs)


async def get_folders(
    telethon_client: TelegramClient | None = None, **kwargs
) -> list[TelegramFolder]:
    telegram_cache = get_telegram_cache(telethon_client=telethon_client)
    return await telegram_cache.get_folders(**kwargs)
