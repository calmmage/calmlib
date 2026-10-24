"""Bot store: the registry of bot identities we own, who claims each, and where its token lives.

The registry is one YAML file (path from ``[bots] registry`` in the telegram config). It holds
identities and claims, never tokens: ``token_key`` is the NAME of a secret. ``bot_token`` resolves
that name at the moment of use and the value never enters the registry, logs or argv.

Status vocabulary::

    free     nobody claims it; a new project may take the token
    busy     claimed by at least one consumer (project / chat); must answer the probe to stay busy
    keep     kept on purpose regardless of claims or probes
    deleted  identity gone in BotFather; the record stays so it is not re-litigated
    foreign  not ours (we only talk to it)

A claim is a ``Consumer``: project (repo path), code, vision, chats [{harness, id}]. Released
claims move to ``history``; nothing is deleted from the file.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from calmlib.telegram.config import get_config

STATUSES = ("free", "busy", "keep", "deleted", "foreign")
TOKEN_STORES = ("calmmage-env", "project-env", "syncthing-share", "unknown", "none")
HEADER = "# telegram bot registry — identities and claims, NEVER tokens (token_key = env key name)\n"


def today() -> str:
    return date.today().strftime("%d %b %Y")  # DD MMM YYYY, zero-padded


@dataclass
class Consumer:
    project: str
    code: str | None = None
    vision: str | None = None
    chats: list[dict[str, str]] = field(default_factory=list)  # {harness, id, resume?}
    since: str | None = None
    note: str | None = None


@dataclass
class Bot:
    username: str
    display_name: str | None = None
    bot_id: int | None = None
    owner_account: str = "unknown"  # primary | secondary | service | unknown
    token_key: str | None = None
    token_key_aliases: list[str] = field(default_factory=list)
    token_store: str = "unknown"
    token_path: str | None = None  # project-env: the .env file that holds it
    status: str = "free"
    consumers: list[Consumer] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    deploy: str | None = None
    ownership_checked: str | None = None  # DD MMM YYYY, BotFather /mybots
    token_checked: str | None = None  # DD MMM YYYY, getMe
    token_check: str | None = None  # ok | invalid | no-key
    probed: str | None = None  # DD MMM YYYY, /start from a user account
    probe: str | None = None  # alive | no-reply | skipped
    last_activity: str | None = None  # legacy scan evidence (ISO date)
    legacy_status: str | None = None  # status in the old registry at migration time
    notes: str | None = None

    @property
    def handle(self) -> str:
        return f"@{self.username}"

    @property
    def counts_against_quota(self) -> bool:
        return self.status not in ("deleted", "foreign")


def registry_path() -> Path:
    path = get_config().registry
    if path is None:
        raise FileNotFoundError("[bots] registry is not set in the telegram config")
    return path


@dataclass
class Registry:
    accounts: dict[str, dict[str, Any]]
    bots: list[Bot]
    provenance: list[str] = field(default_factory=list)
    version: int = 2

    @classmethod
    def load(cls, path: Path | None = None) -> Registry:
        import yaml

        raw = yaml.safe_load((path or registry_path()).read_text()) or {}
        bots = []
        for b in raw.get("bots", []):
            b = dict(b)
            b["consumers"] = [Consumer(**c) for c in b.get("consumers", [])]
            bots.append(Bot(**b))
        return cls(accounts=raw.get("accounts", {}), bots=bots, provenance=raw.get("provenance", []),
                   version=raw.get("version", 2))

    def save(self, path: Path | None = None) -> None:
        import yaml

        def clean(d: dict) -> dict:
            return {k: v for k, v in d.items() if v not in (None, [], {}, "")}

        data = {
            "version": self.version,
            "provenance": self.provenance,
            "accounts": self.accounts,
            "bots": [clean({**asdict(b), "consumers": [clean(asdict(c)) for c in b.consumers]})
                     for b in sorted(self.bots, key=lambda b: b.username.lower())],
        }
        (path or registry_path()).write_text(
            HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120))

    def get(self, ref: str) -> Bot | None:
        """By @username, token key name (or alias) or bot id."""
        ref = ref.lstrip("@")
        for b in self.bots:
            if (b.username.lower() == ref.lower() or ref.upper() in {b.token_key or "", *b.token_key_aliases}
                    or (b.bot_id and str(b.bot_id) == ref)):
                return b
        return None

    def quota(self, account: str) -> tuple[int, int | None]:
        used = sum(1 for b in self.bots if b.owner_account == account and b.counts_against_quota)
        return used, self.accounts.get(account, {}).get("bot_cap")

    def free(self) -> list[Bot]:
        return [b for b in self.bots if b.status == "free"]

    def owned_by(self, account: str) -> list[Bot]:
        return [b for b in self.bots if b.owner_account == account]


def resolve_secret(name: str) -> str | None:
    """A secret by name: the process environment, then the ``keys`` store when installed."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        from keys import resolve  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        if exc.name != "keys":
            raise
        return None
    return resolve(name)


def bot_token(ref: str, registry: Registry | None = None, resolve=resolve_secret) -> str | None:
    """A bot's token, looked up by its key name at the moment of use. Never printed or stored."""
    bot = (registry or Registry.load()).get(ref)
    if bot is None:
        raise KeyError(f"{ref}: not in the bot registry")
    for name in (bot.token_key, *bot.token_key_aliases):
        if name:
            value = resolve(name)
            if value:
                return value
    return None
