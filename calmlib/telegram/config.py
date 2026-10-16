"""Where local Telegram lives on this machine: accounts, cache, archive, bot registry.

The code is public, so everything personal sits in one small TOML file. Lookup order:
``$CALMLIB_TELEGRAM_CONFIG``, ``~/calm/config/telegram/telegram.toml``,
``~/.config/calmlib/telegram.toml``. Missing file = empty config: every value has a default
or is reported as "not set".

Example::

    [accounts]            # account name -> Telegram user id; binds the cache before any read
    primary = 111
    secondary = 222

    [cache]
    mongo = "mongodb://localhost:27017"
    db = "telegram_cache"
    files = "~/data/telegram"        # JSON side cache: <files>/<user id>/dialog_*.json

    [archive]
    root = "/Volumes/nas/telegram"   # NAS export: <root>/<account>/<chat id>__<title>/messages.jsonl

    [bots]
    registry = "~/bots/registry.yaml"
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ENV_VAR = "CALMLIB_TELEGRAM_CONFIG"
SEARCH_PATHS = (
    Path("~/calm/config/telegram/telegram.toml"),
    Path("~/.config/calmlib/telegram.toml"),
)


class AccountNotBound(RuntimeError):
    """The account's Telegram user id is unknown: no collection may be named."""


class AccountMismatch(RuntimeError):
    """The logged-in Telegram user is not the account the cache is bound to."""


@dataclass(frozen=True)
class TelegramConfig:
    path: Path | None = None
    accounts: dict[str, int] = field(default_factory=dict)
    mongo: str = "mongodb://localhost:27017"
    db: str = "telegram_cache"
    files: Path | None = None
    archive: Path | None = None
    registry: Path | None = None

    def account_id(self, account: str) -> int | None:
        return self.accounts.get(account)


def _path(value) -> Path | None:
    return Path(os.path.expanduser(str(value))) if value else None


def config_path() -> Path | None:
    explicit = os.environ.get(ENV_VAR)
    if explicit:
        return Path(os.path.expanduser(explicit))
    for candidate in SEARCH_PATHS:
        candidate = candidate.expanduser()
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=None)
def _load(path: Path | None) -> TelegramConfig:
    if path is None or not path.is_file():
        return TelegramConfig(path=path)
    data = tomllib.loads(path.read_text())
    accounts = {}
    for name, value in (data.get("accounts") or {}).items():
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{path}: [accounts] {name} must be a positive integer user id")
        accounts[name] = value
    cache = data.get("cache") or {}
    return TelegramConfig(
        path=path,
        accounts=accounts,
        mongo=cache.get("mongo") or TelegramConfig.mongo,
        db=cache.get("db") or TelegramConfig.db,
        files=_path(cache.get("files")),
        archive=_path((data.get("archive") or {}).get("root")),
        registry=_path((data.get("bots") or {}).get("registry")),
    )


def get_config() -> TelegramConfig:
    """The current machine's config (re-read when the env var points elsewhere)."""
    return _load(config_path())
