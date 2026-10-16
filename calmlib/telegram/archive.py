"""The full-history archive: the daily NAS export, read-only.

Layout (written by the exporter, never by this module)::

    <root>/<account>/<chat id>__<title>/messages.jsonl      one JSON message per line, append-only
    <root>/<account>/<chat id>__<title>/media/<YYYY>/<message id>_<name | kind.ext>
    <state>/<account>.sqlite                                 the exporter's index: chats, media

Chat ids are peer ids (``-100…`` for channels and supergroups, negative for basic groups).
Lookups go through the index first, so finding a chat or a file never scans the NAS.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from calmlib.telegram.config import get_config


class ArchiveUnavailable(RuntimeError):
    """The archive root or its index is not configured, not mounted or missing."""


def to_int(value) -> int:
    """Telegram 64-bit ids as the exporter writes them: plain ints or {low, high} pairs."""
    if isinstance(value, dict) and "low" in value:
        return value["high"] * (1 << 32) + (value["low"] & 0xFFFFFFFF)
    return int(value)


def account_root(account: str) -> Path:
    root = get_config().archive
    if root is None:
        raise ArchiveUnavailable("[archive] root is not set in the telegram config")
    if not root.exists():
        raise ArchiveUnavailable(f"archive not mounted: {root}")
    return root / account


def index(account: str) -> sqlite3.Connection:
    """The exporter's own index, opened read-only."""
    state = get_config().archive_state
    if state is None:
        raise ArchiveUnavailable("[archive] state is not set in the telegram config")
    path = state / f"{account}.sqlite"
    if not path.is_file():
        raise ArchiveUnavailable(f"no archive index for {account}: {path}")
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    return db


@dataclass(frozen=True)
class ArchivedChat:
    chat_id: int
    title: str
    kind: str
    dir: str
    messages: int
    complete: bool


def chats(account: str) -> list[ArchivedChat]:
    with index(account) as db:
        rows = db.execute(
            "select id, title, kind, dir, messages_n, history_complete from chats order by messages_n desc"
        ).fetchall()
    return [ArchivedChat(r["id"], r["title"] or "", r["kind"] or "", r["dir"] or "", r["messages_n"] or 0,
                         bool(r["history_complete"])) for r in rows]


def chat_dir(account: str, chat_id: int) -> Path | None:
    """The chat's folder, from the index when there is one, else by name prefix."""
    try:
        with index(account) as db:
            row = db.execute("select dir from chats where id = ?", (int(chat_id),)).fetchone()
        if row and row["dir"]:
            return account_root(account) / row["dir"]
    except ArchiveUnavailable:
        pass
    found = sorted(account_root(account).glob(f"{int(chat_id)}__*"))
    return found[0] if found else None


def read_lines(path: Path, offset: int = 0) -> Iterator[tuple[dict, int]]:
    """Messages from one messages.jsonl, resumable: yields (message, offset after it).

    A line still being written (no newline yet) is left for the next call. If the file is
    shorter than the saved offset it was rewritten, so reading starts over.
    """
    if offset > path.stat().st_size:
        offset = 0
    with path.open("rb") as f:
        f.seek(offset)
        while True:
            line = f.readline()
            if not line or not line.endswith(b"\n"):
                return
            yield json.loads(line), f.tell()


def messages(account: str, chat_id: int, offset: int = 0) -> Iterator[tuple[dict, int]]:
    """A chat's archived messages in file order (see read_lines)."""
    folder = chat_dir(account, chat_id)
    if folder is None:
        return
    path = folder / "messages.jsonl"
    if path.is_file():
        yield from read_lines(path, offset)


@dataclass(frozen=True)
class ArchivedMedia:
    chat_id: int
    message_id: int
    kind: str
    status: str  # done | pending | failed
    path: Path | None
    bytes: int | None


def media(account: str, chat_id: int, message_id: int | None = None) -> list[ArchivedMedia]:
    """Media the exporter knows for a chat (or one message): saved files and still-pending ones."""
    query = "select chat_id, msg_id, kind, status, path, bytes from media where chat_id = ?"
    args: list = [int(chat_id)]
    if message_id is not None:
        query += " and msg_id = ?"
        args.append(int(message_id))
    with index(account) as db:
        rows = db.execute(query + " order by msg_id desc", args).fetchall()
    return [ArchivedMedia(r["chat_id"], r["msg_id"], r["kind"] or "", r["status"] or "",
                          Path(r["path"]) if r["path"] else None, r["bytes"]) for r in rows]


def summary(account: str) -> dict:
    """Counts only, from the index: chats, messages, media by status, last export run."""
    with index(account) as db:
        chats_n, messages_n, complete = db.execute(
            "select count(*), coalesce(sum(messages_n), 0), coalesce(sum(history_complete), 0) from chats"
        ).fetchone()
        by_status = dict(db.execute("select status, count(*) from media group by status").fetchall())
        last = db.execute("select max(finished_at) from runs where ok = 1").fetchone()[0]
    return {"chats": chats_n, "messages": messages_n, "complete": complete, "media": by_status, "last_run": last}
