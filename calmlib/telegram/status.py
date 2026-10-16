"""What local Telegram holds on this machine, per account. Offline and read-only.

No Telegram network, no session opened, no message text read: counts, dates and file ages
only. Every source has a short timeout, so a sleeping NAS or a stopped Mongo shows up as a
line instead of a hang.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from calmlib.telegram.config import TelegramConfig, get_config
from calmlib.telegram.store import collection_name

ACCOUNTS = ("primary", "secondary", "service")
SESSIONS_DIR = Path.home() / ".calmmage" / "telethon_sessions"
STALE_CACHE = dt.timedelta(hours=6)
STALE_ARCHIVE = dt.timedelta(days=2)


@dataclass
class Source:
    """One store's answer for one account: ok, or why not."""

    ok: bool = False
    note: str = ""
    count: int | None = None
    chats: int | None = None
    newest: dt.datetime | None = None
    names: list[str] = field(default_factory=list)


@dataclass
class AccountStatus:
    account: str
    user_id: int | None
    session: Source
    cache: Source
    files: Source
    folders: Source
    archive: Source


@dataclass
class Status:
    config: TelegramConfig
    accounts: list[AccountStatus]
    bots: Source
    warnings: list[str]


def _timeout(seconds, fn, *args):
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(fn, *args).result(timeout=seconds)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _mtime(path: Path) -> dt.datetime:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, tz=dt.timezone.utc)


def _session(account: str) -> Source:
    path = SESSIONS_DIR / f"{account}.session"
    if not path.exists():
        return Source(note="no session")
    mode = stat.S_IMODE(path.stat().st_mode)
    return Source(ok=True, newest=_mtime(path), note="readable by others" if mode & 0o077 else "")


def _mongo_counts(config: TelegramConfig, user_ids: list[int]) -> dict[int, Source]:
    from pymongo import MongoClient

    client = MongoClient(config.mongo, serverSelectionTimeoutMS=1500, connectTimeoutMS=1500)
    try:
        db = client[config.db]
        out = {}
        for uid in user_ids:
            col = db[collection_name(uid)]
            count = col.estimated_document_count()
            if not count:
                out[uid] = Source(note="no messages")
                continue
            newest = next(iter(col.find({}, {"date": 1, "_id": 0}).sort("date", -1).limit(1)), {})
            date = newest.get("date")
            if isinstance(date, str):
                date = dt.datetime.fromisoformat(date)
            out[uid] = Source(ok=True, count=count, chats=len(col.distinct("chat_id")), newest=date)
        return out
    finally:
        client.close()


def _files(config: TelegramConfig, uid: int) -> tuple[Source, Source]:
    """Chats and folders from the JSON side cache (<files>/<user id>/dialog_*.json)."""
    if config.files is None:
        return Source(note="[cache] files not set"), Source(note="[cache] files not set")
    root = config.files / str(uid)
    entities, filters = root / "dialog_entities.json", root / "dialog_filters.json"
    chats = Source(note="no dialog list")
    if entities.exists():
        chats = Source(ok=True, chats=len(json.loads(entities.read_text())), newest=_mtime(entities))
    folders = Source(note="no folder list")
    if filters.exists():
        data = json.loads(filters.read_text())
        names = []
        for f in data.get("filters", []):
            if f.get("_") != "DialogFilter":
                continue
            title = f.get("title")
            names.append(title.get("text", "") if isinstance(title, dict) else str(title or ""))
        folders = Source(ok=True, count=len(names), names=names, newest=_mtime(filters))
    return chats, folders


def _archive(config: TelegramConfig, account: str) -> Source:
    root = config.archive
    if root is None:
        return Source(note="[archive] root not set")

    def look():
        if not root.exists():
            return Source(note="not mounted")
        folder = root / account
        if not folder.is_dir():
            return Source(note="no account folder")
        try:  # the exporter's index: counts without touching the NAS
            from calmlib.telegram import archive

            info = archive.summary(account)
        except Exception:
            return Source(ok=True, newest=_mtime(folder))
        last = dt.datetime.fromisoformat(info["last_run"]) if info["last_run"] else _mtime(folder)
        return Source(ok=True, count=info["messages"], chats=info["chats"], newest=last,
                      names=[f"{n} {s}" for s, n in sorted(info["media"].items())])

    try:
        return _timeout(3, look)
    except concurrent.futures.TimeoutError:
        return Source(note="NAS: no answer in 3 s")


def _bots(config: TelegramConfig) -> Source:
    if config.registry is None:
        return Source(note="[bots] registry not set")
    if not config.registry.exists():
        return Source(note=f"no registry at {config.registry}")
    try:
        import yaml
    except ImportError:
        return Source(note="pyyaml not installed")
    data = yaml.safe_load(config.registry.read_text()) or {}
    bots = data.get("bots") or {}
    rows = bots.values() if isinstance(bots, dict) else bots
    by_status: dict[str, int] = {}
    for bot in rows:
        key = (bot or {}).get("status", "?") if isinstance(bot, dict) else "?"
        by_status[key] = by_status.get(key, 0) + 1
    names = [f"{n} {s}" for s, n in sorted(by_status.items(), key=lambda kv: -kv[1])]
    return Source(ok=True, count=sum(by_status.values()), names=names, newest=_mtime(config.registry))


def collect(now: dt.datetime | None = None) -> Status:
    config = get_config()
    now = now or dt.datetime.now(dt.timezone.utc)
    names = list(dict.fromkeys([*ACCOUNTS, *config.accounts]))
    ids = [config.account_id(a) for a in names]

    try:
        mongo = _timeout(5, _mongo_counts, config, [i for i in ids if i])
        mongo_note = ""
    except Exception as e:  # stopped Docker, refused port, timeout
        mongo, mongo_note = {}, f"Mongo: {type(e).__name__}"

    warnings = []
    accounts = []
    for account, uid in zip(names, ids):
        session = _session(account)
        if session.note:
            warnings.append(f"{account}: session file {session.note} (chmod 600)")
        if uid is None:
            empty = Source(note="no user id in config")
            accounts.append(AccountStatus(account, None, session, empty, empty, empty, _archive(config, account)))
            continue
        cache = mongo.get(uid) or Source(note=mongo_note or "no messages")
        files, folders = _files(config, uid)
        archive = _archive(config, account)
        accounts.append(AccountStatus(account, uid, session, cache, files, folders, archive))
        if account == "primary" and cache.newest and now - cache.newest > STALE_CACHE:
            warnings.append(f"primary: cache's newest message is {age(cache.newest, now)} old")
        if archive.newest and now - archive.newest > STALE_ARCHIVE:
            warnings.append(f"{account}: last archive export {age(archive.newest, now)} ago")
    if mongo_note:
        warnings.append(f"{mongo_note} at {config.mongo}")
    return Status(config=config, accounts=accounts, bots=_bots(config), warnings=warnings)


def _age(delta: dt.timedelta) -> str:
    s = int(delta.total_seconds())
    if s < 3600:
        return f"{max(s // 60, 1)} min"
    if s < 2 * 86400:
        return f"{s // 3600} h"
    return f"{s // 86400} d"


def age(when: dt.datetime | None, now: dt.datetime | None = None) -> str:
    if when is None:
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    return _age((now or dt.datetime.now(dt.timezone.utc)) - when)


def as_dict(status: Status) -> dict:
    """JSON-friendly view for agents (`tgl status --json`)."""

    def src(s: Source):
        d = {k: v for k, v in s.__dict__.items() if v not in (None, "", [])}
        if s.newest:
            d["newest"] = s.newest.isoformat()
        return d

    return {
        "config": str(status.config.path) if status.config.path else None,
        "accounts": [
            {"account": a.account, "user_id": a.user_id,
             **{k: src(getattr(a, k)) for k in ("session", "cache", "files", "folders", "archive")}}
            for a in status.accounts
        ],
        "bots": src(status.bots),
        "warnings": status.warnings,
    }


def host() -> str:
    return os.uname().nodename.split(".")[0]
