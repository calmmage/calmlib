"""Telegram folders (dialog filters) of a user account: read them, create or update one by title.

Offline: ``cached_folders`` reads the side cache TelegramCache writes (``dialog_filters.json``).
Live: ``list_folders`` and ``upsert_folder`` take an open Telethon client, so the caller decides
which account and holds the session lock (``get_telethon_client_context(account=...)``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from calmlib.telegram.config import get_config


def title_text(title) -> str:
    """Folder titles are plain strings in old layers, TextWithEntities (object or dict) in new ones."""
    if isinstance(title, dict):
        return str(title.get("text", ""))
    return str(getattr(title, "text", title) or "")


@dataclass(frozen=True)
class Folder:
    id: int
    title: str
    emoticon: str | None
    chats: int  # explicitly included chats (pinned + included)
    excluded: int


def _folder(f) -> Folder | None:
    get = f.get if isinstance(f, dict) else lambda k, d=None: getattr(f, k, d)
    kind = get("_") if isinstance(f, dict) else type(f).__name__
    if kind != "DialogFilter":  # DialogFilterDefault ("All chats") and chatlists are not editable here
        return None
    return Folder(
        id=int(get("id") or 0),
        title=title_text(get("title")),
        emoticon=get("emoticon"),
        chats=len(get("pinned_peers") or []) + len(get("include_peers") or []),
        excluded=len(get("exclude_peers") or []),
    )


def cached_folders(user_id: int) -> list[Folder]:
    """Folders as last saved by TelegramCache for this user id. No network."""
    files = get_config().files
    if files is None:
        return []
    path = files / str(user_id) / "dialog_filters.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    rows = data.get("filters", []) if isinstance(data, dict) else data
    return [f for f in (_folder(r) for r in rows) if f]


async def _filters(client) -> list:
    from telethon.tl.functions.messages import GetDialogFiltersRequest

    result = await client(GetDialogFiltersRequest())
    return list(getattr(result, "filters", result))


async def list_folders(client) -> list[Folder]:
    return [f for f in (_folder(r) for r in await _filters(client)) if f]


async def upsert_folder(client, title: str, *, bots=(), chats=(), emoticon: str | None = None,
                        start_bots: bool = False) -> dict:
    """Make the folder ``title`` hold exactly these bots (usernames) and chats (ids or usernames).

    Re-running updates the same folder instead of adding a second one. A folder can only hold
    chats that exist: a bot never started is reported in ``bots_not_started``, unless
    ``start_bots`` is set, which sends it /start first. Returns counts and what was not found.
    """
    from telethon.tl.functions.messages import UpdateDialogFilterRequest
    from telethon.tl.types import DialogFilter, TextWithEntities

    dialogs = {d.id for d in await client.get_dialogs(limit=None)}
    peers, not_found, not_started = [], [], []
    for username in dict.fromkeys(bots):
        entity = await client.get_entity(username)
        if entity.id not in dialogs:
            if not start_bots:
                not_started.append(username)
                continue
            await client.send_message(entity, "/start")
        peers.append(await client.get_input_entity(entity))
    added_bots = len(peers)
    for chat in dict.fromkeys(chats):
        try:
            peers.append(await client.get_input_entity(chat))
        except (ValueError, TypeError):
            not_found.append(chat)

    filters = await _filters(client)
    existing = next((f for f in filters if type(f).__name__ == "DialogFilter" and title_text(f.title) == title), None)
    used = {f.id for f in filters if hasattr(f, "id")}
    folder_id = existing.id if existing else next(i for i in range(2, 256) if i not in used)
    folder = DialogFilter(id=folder_id, title=TextWithEntities(title, []), pinned_peers=[],
                          include_peers=peers, exclude_peers=[], emoticon=emoticon)
    await client(UpdateDialogFilterRequest(id=folder_id, filter=folder))
    return {"folder": title, "id": folder_id, "bots": added_bots, "chats": len(peers) - added_bots,
            "chats_not_found": not_found, "bots_not_started": not_started, "updated_existing": bool(existing)}
