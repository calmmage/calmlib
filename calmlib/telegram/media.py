"""Media library: find a message's file in the archive first, download it only when missing.

    path = media.archived_file("primary", chat_id, message_id)        # offline, no NAS scan
    async with get_telethon_client_context(account="primary") as client:
        path = await media.get_file("primary", chat_id, message_id, client=client)

Downloads land in the side cache, ``<files>/<user id>/media/<chat id>/<message id>_<name>``,
never in the archive (the exporter owns it).
"""

from __future__ import annotations

from pathlib import Path

from calmlib.telegram import archive
from calmlib.telegram.config import get_config
from calmlib.telegram.store import account_user_id


def archived_file(account: str, chat_id: int, message_id: int) -> Path | None:
    """The archived file for one message, when the exporter has saved it and it is reachable."""
    try:
        found = archive.media(account, chat_id, message_id)
    except archive.ArchiveUnavailable:
        return None
    for item in found:
        if item.status == "done" and item.path and item.path.exists():
            return item.path
    return None


def download_dir(account: str, chat_id: int) -> Path:
    files = get_config().files
    if files is None:
        raise archive.ArchiveUnavailable("[cache] files is not set in the telegram config")
    return files / str(account_user_id(account)) / "media" / str(int(chat_id))


def downloaded_file(account: str, chat_id: int, message_id: int) -> Path | None:
    folder = download_dir(account, chat_id)
    found = sorted(folder.glob(f"{int(message_id)}_*")) if folder.is_dir() else []
    return next((p for p in found if not p.name.endswith(".part")), None)


async def get_file(account: str, chat_id: int, message_id: int, client=None) -> Path | None:
    """Archive, then earlier downloads, then Telegram (needs ``client`` for that account)."""
    path = archived_file(account, chat_id, message_id) or downloaded_file(account, chat_id, message_id)
    if path or client is None:
        return path
    message = await client.get_messages(int(chat_id), ids=int(message_id))
    if message is None or not getattr(message, "media", None):
        return None
    folder = download_dir(account, chat_id)
    folder.mkdir(parents=True, exist_ok=True)
    file = getattr(message, "file", None)
    name = (getattr(file, "name", None) or f"media{getattr(file, 'ext', None) or ''}").replace("/", "_")
    part = folder / f"{int(message_id)}_{name}.part"
    got = await client.download_media(message, file=str(part))
    if not got or not Path(got).is_file():
        return None
    final = part.with_name(part.name.removesuffix(".part"))
    Path(got).replace(final)
    return final
