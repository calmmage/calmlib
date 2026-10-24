"""Telegram bot inventory — which bots we own, which are alive, how many slots are left.

Two independent questions, two independent sources:

1. **Ownership** — "which bots does this account own?" Only @BotFather knows. There is no
   Bot API or MTProto method for it, so we drive BotFather's `/mybots` inline keyboard with a
   telethon *user* client and read the button labels. Read-only: we click page-navigation
   buttons only, never a bot's settings/delete buttons.

2. **Activity** — "is anything actually using this bot?" Derived from message history visible
   to the user account: last message *from the bot* in its DM, else last message from that bot
   anywhere in the dialog list, else nothing ever seen.

Both are needed to answer the real question — "which BotFather slots are safe to reclaim?" —
because ownership without activity is just a list of names, and a bot that never messages the
owner looks identical to a bot that does not exist.

Used by `tools/automations/telegram_bots/cli.py`. See the `telegram-bots` skill.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from loguru import logger
from telethon import TelegramClient

from calmlib.telegram.chat_utils import chat_is_bot
from calmlib.telegram.telethon_client import get_telethon_client_context

BOTFATHER = "BotFather"

#: Telegram's default per-account bot cap. Accounts can be raised above this by support;
#: the only authoritative answer is BotFather's own refusal message on `/newbot`.
DEFAULT_BOT_CAP = 20

#: Button labels BotFather uses to page through a long `/mybots` list.
_NEXT_PAGE_LABELS = ("»", "▶", ">>", "Next")

_USERNAME_RE = re.compile(r"@([A-Za-z0-9_]{4,32})")


@dataclass
class OwnedBot:
    """A bot that BotFather lists under this account."""

    username: str
    owner_account: str

    def __str__(self) -> str:
        return f"@{self.username}"


@dataclass
class BotActivity:
    """Last-seen evidence for one bot, from the perspective of one user account."""

    username: str
    last_activity: datetime | None = None
    #: "from_bot" (message authored by the bot), "dm_any" (any message in its DM),
    #: or "none" (never seen).
    signal: str = "none"
    #: Human-readable chat title where the signal was found.
    where: str | None = None
    bot_id: int | None = None

    @property
    def age_days(self) -> int | None:
        if self.last_activity is None:
            return None
        now = datetime.now(timezone.utc)
        return (now - self.last_activity).days


@dataclass
class InventoryResult:
    account: str
    owned: list[OwnedBot] = field(default_factory=list)
    activity: dict[str, BotActivity] = field(default_factory=dict)
    scanned_dialogs: int = 0
    scanned_at: datetime | None = None

    @property
    def cap_used(self) -> int:
        return len(self.owned)


def _normalize(username: str) -> str:
    """`@Foo_bot` / `https://t.me/Foo_bot` → `Foo_bot`. Case preserved."""
    username = username.strip()
    username = username.rsplit("/", 1)[-1]
    return username.lstrip("@")


def _buttons(message) -> list:
    """Flatten a message's inline keyboard into a list of buttons."""
    rows = getattr(message, "buttons", None) or []
    return [button for row in rows for button in row]


def _usernames_from_buttons(message) -> list[str]:
    found = []
    for button in _buttons(message):
        text = (getattr(button, "text", "") or "").strip()
        match = _USERNAME_RE.fullmatch(text)
        if match:
            found.append(match.group(1))
    return found


def _next_page_label(message) -> str | None:
    for button in _buttons(message):
        text = (getattr(button, "text", "") or "").strip()
        if text in _NEXT_PAGE_LABELS:
            return text
    return None


async def list_owned_bots(
    account: str = "primary",
    *,
    max_pages: int = 20,
    page_delay_sec: float = 1.0,
    client: TelegramClient | None = None,
) -> list[OwnedBot]:
    """Ask @BotFather which bots this account owns.

    Drives the `/mybots` inline keyboard: read the `@name_bot` button labels, click the
    next-page button, re-read the (edited) message, repeat until no new names appear.

    This *sends a message to BotFather* and clicks navigation buttons — harmless, but not
    free of side effects, and it leaves a `/mybots` entry in the BotFather chat.

    Raises RuntimeError if BotFather does not answer with a keyboard (e.g. flood-waited).
    """
    if client is not None:
        return await _list_owned_bots(client, account, max_pages, page_delay_sec)
    async with get_telethon_client_context(account) as owned_client:
        return await _list_owned_bots(owned_client, account, max_pages, page_delay_sec)


async def _list_owned_bots(
    client: TelegramClient,
    account: str,
    max_pages: int,
    page_delay_sec: float,
) -> list[OwnedBot]:
    async with client.conversation(BOTFATHER, timeout=60) as conv:
        await conv.send_message("/mybots")
        message = await conv.get_response()

    if not _buttons(message):
        raise RuntimeError(
            f"BotFather answered /mybots without an inline keyboard: {message.text!r}"
        )

    seen: list[str] = []
    seen_set: set[str] = set()
    for page in range(max_pages):
        page_names = _usernames_from_buttons(message)
        fresh = [name for name in page_names if name not in seen_set]
        seen.extend(fresh)
        seen_set.update(fresh)
        logger.debug(
            f"/mybots page {page + 1}: {len(page_names)} shown, {len(fresh)} new"
        )

        label = _next_page_label(message)
        if not label or not fresh:
            break

        await message.click(text=label)
        await asyncio.sleep(page_delay_sec)
        message = await client.get_messages(BOTFATHER, ids=message.id)
        if message is None:
            break

    return [OwnedBot(username=name, owner_account=account) for name in seen]


async def scan_bot_activity(
    usernames: list[str],
    account: str = "primary",
    *,
    dm_lookback: int = 30,
    dialog_limit: int | None = None,
    client: TelegramClient | None = None,
) -> dict[str, BotActivity]:
    """Find the most recent evidence of life for each bot.

    Two passes:
      1. **All dialogs** — the last message of every dialog; if a target bot wrote it, that is
         a `from_bot` hit (this is what catches bots that only post into groups/channels).
      2. **Bot DMs** — the last `dm_lookback` messages in each target bot's own DM, looking for
         the newest one authored by the bot; falls back to `dm_any` if the DM has messages but
         none from the bot.

    Known blind spot (inherited from the 2026-07-23 scan): pass 1 only inspects each dialog's
    *last* message, so a bot that posts into a busy group looks staler than it is. Raise
    `dm_lookback` or scan specific chats when a verdict matters.

    Returns a dict keyed by the normalized username, one entry per requested bot.
    """
    if client is not None:
        activity, _ = await _scan_bot_activity(
            client, usernames, dm_lookback, dialog_limit
        )
        return activity
    async with get_telethon_client_context(account) as scan_client:
        activity, _ = await _scan_bot_activity(
            scan_client, usernames, dm_lookback, dialog_limit
        )
        return activity


async def _scan_bot_activity(
    client: TelegramClient,
    usernames: list[str],
    dm_lookback: int,
    dialog_limit: int | None,
) -> tuple[dict[str, BotActivity], int]:
    """Returns (activity by username, number of dialogs scanned)."""
    targets = [_normalize(u) for u in usernames]
    activity = {name: BotActivity(username=name) for name in targets}

    # Resolve usernames → bot ids. Some may be gone (deleted bot, renamed) — keep going.
    id_to_name: dict[int, str] = {}
    for name in targets:
        try:
            entity = await client.get_entity(name)
        except Exception as exc:  # noqa: BLE001 - one bad username must not kill the scan
            logger.warning(f"could not resolve @{name}: {exc}")
            continue
        activity[name].bot_id = entity.id
        id_to_name[entity.id] = name

    def record(name: str, when: datetime, signal: str, where: str | None) -> None:
        entry = activity[name]
        if entry.last_activity is None or when > entry.last_activity:
            entry.last_activity, entry.signal, entry.where = when, signal, where
        elif entry.signal == "none":
            entry.signal, entry.where = signal, where

    # Pass 1 — every dialog's last message.
    scanned = 0
    async for dialog in client.iter_dialogs(limit=dialog_limit):
        scanned += 1
        message = dialog.message
        if message is None:
            continue
        sender_id = getattr(message, "sender_id", None)
        name = id_to_name.get(sender_id) if sender_id is not None else None
        if name:
            record(name, message.date, "from_bot", dialog.name)

    # Pass 2 — each bot's own DM, deeper.
    for name in targets:
        bot_id = activity[name].bot_id
        if bot_id is None:
            continue
        try:
            messages = await client.get_messages(bot_id, limit=dm_lookback)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"could not read DM with @{name}: {exc}")
            continue
        for message in messages:  # newest first
            if getattr(message, "sender_id", None) == bot_id:
                record(name, message.date, "from_bot", "dm")
                break
        else:
            if messages:
                record(name, messages[0].date, "dm_any", "dm")

    logger.info(f"scanned {scanned} dialogs for {len(targets)} bots")
    return activity, scanned


async def collect_inventory(
    account: str = "primary",
    *,
    extra_usernames: list[str] | None = None,
    use_botfather: bool = True,
    dm_lookback: int = 30,
    dialog_limit: int | None = None,
) -> InventoryResult:
    """Full sweep: owned bots (BotFather) + activity for each, on one telethon client.

    `extra_usernames` adds bots to the activity scan that BotFather does not list — bots owned
    by another account, or ones we only interact with. They are scanned but not counted
    against this account's quota.

    With `use_botfather=False`, only `extra_usernames` are scanned (no BotFather contact) —
    use this for a cheap activity refresh of already-known bots.
    """
    extra = [_normalize(u) for u in (extra_usernames or [])]
    async with get_telethon_client_context(account) as client:
        owned = await list_owned_bots(account, client=client) if use_botfather else []
        names = list(dict.fromkeys([bot.username for bot in owned] + extra))
        activity, scanned = await _scan_bot_activity(
            client, names, dm_lookback, dialog_limit
        )

    return InventoryResult(
        account=account,
        owned=owned,
        activity=activity,
        scanned_dialogs=scanned,
        scanned_at=datetime.now(timezone.utc),
    )


async def find_bot_dialogs(account: str = "primary", limit: int | None = None) -> list:
    """Every bot DM visible to this account (owned or not) — the wide net.

    Complements `list_owned_bots`, which only sees bots we created.
    """
    dialogs = []
    async with get_telethon_client_context(account) as client:
        async for dialog in client.iter_dialogs(limit=limit):
            if chat_is_bot(dialog.entity):
                dialogs.append(dialog)
    return dialogs
