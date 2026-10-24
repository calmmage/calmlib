"""Account isolation: a cache only ever names, reads or writes its own account's collection.

No network, no real Mongo, no real session: a stand-in database records every operation by
collection, a stand-in Telethon client answers get_me.
"""

import asyncio
from types import SimpleNamespace

import pytest

from calmlib.telegram import config as tg_config
from calmlib.telegram.config import AccountMismatch, AccountNotBound
from calmlib.telegram.telegram_cache import TelegramCache
from calmlib.utils.utils import Singleton

PRIMARY, SECONDARY = 111, 222


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, *a, **k):
        return self

    def skip(self, n):
        return self

    def limit(self, n):
        return self

    def __aiter__(self):
        self._it = iter(self.rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class Collection:
    def __init__(self, name, log, rows):
        self.name, self.log, self.rows = name, log, rows

    def _op(self, op):
        self.log.append((self.name, op))

    async def create_index(self, *a, **k):
        self._op("index")

    def find(self, query):
        self._op("find")
        return Cursor([r for r in self.rows if r["chat_id"] == query["chat_id"]])

    async def find_one(self, query):
        self._op("find_one")
        return next((r for r in self.rows if r["chat_id"] == query["chat_id"]), None)

    async def delete_many(self, query):
        self._op("delete")


class Database:
    """Two accounts' collections with the same chat and message numbers."""

    def __init__(self):
        self.log, self.named = [], []
        self.data = {
            f"messages_user_{uid}": [
                {"_": "Message", "id": 7, "chat_id": 5, "message": f"from {uid}",
                 "date": "2026-10-16T10:00:00+00:00", "peer_id": {"_": "PeerUser", "user_id": 5}}
            ]
            for uid in (PRIMARY, SECONDARY)
        }

    def __getitem__(self, name):
        self.named.append(name)
        return Collection(name, self.log, self.data.get(name, []))


class FakeClientContext:
    def __init__(self, user_id):
        self.user_id, self.opened = user_id, 0

    async def __aenter__(self):
        if self.user_id is None:
            raise ConnectionError("no session file")
        self.opened += 1
        return SimpleNamespace(get_me=self._me)

    async def _me(self):
        return SimpleNamespace(id=self.user_id)

    async def __aexit__(self, *exc):
        return False


@pytest.fixture
def make_cache(tmp_path, monkeypatch):
    def make(account, accounts, client_user_id, env_user_id=None):
        conf = tmp_path / "telegram.toml"
        conf.write_text("[accounts]\n" + "".join(f"{k} = {v}\n" for k, v in accounts.items()))
        monkeypatch.setenv(tg_config.ENV_VAR, str(conf))
        tg_config._load.cache_clear()
        for key in ("CALMMAGE_TELEGRAM_USER_ID",):
            if env_user_id is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, str(env_user_id))
        Singleton._instances.pop(TelegramCache, None)
        cache = TelegramCache(telethon_account=account, mongo_enabled=True, root_path=tmp_path / "files")
        db = Database()
        cache._mongo_client = {cache.db_name: db}
        cache._telethon_client_cm._inner = FakeClientContext(client_user_id)
        return cache, db

    yield make
    Singleton._instances.pop(TelegramCache, None)
    tg_config._load.cache_clear()


def run(coro):
    return asyncio.run(coro)


def read(cache):
    async def go():
        assert await cache._has_cached_messages(5)
        return await cache._load_messages_from_mongo(5, limit=10)

    return run(go())


@pytest.mark.parametrize(
    "account,own,other",
    [("secondary", SECONDARY, PRIMARY), ("primary", PRIMARY, SECONDARY)],
)
def test_wrong_env_key_never_picks_the_collection(make_cache, account, own, other):
    cache, db = make_cache(
        account, {"primary": PRIMARY, "secondary": SECONDARY}, client_user_id=own, env_user_id=other
    )
    messages = read(cache)
    assert [m.message for m in messages] == [f"from {own}"]
    assert {name for name, _ in db.log} == {f"messages_user_{own}"}
    assert f"messages_user_{other}" not in db.named
    assert cache._telethon_client_cm._inner.opened == 0  # cached read: no client, no network


def test_no_map_entry_uses_the_clients_own_id_first(make_cache):
    cache, db = make_cache("secondary", {"primary": PRIMARY}, client_user_id=SECONDARY, env_user_id=PRIMARY)
    messages = read(cache)
    assert [m.message for m in messages] == [f"from {SECONDARY}"]
    assert db.named and set(db.named) == {f"messages_user_{SECONDARY}"}


def test_no_map_entry_and_no_client_is_refused_before_any_collection(make_cache):
    cache, db = make_cache("service", {"primary": PRIMARY}, client_user_id=None, env_user_id=PRIMARY)
    with pytest.raises(AccountNotBound):
        read(cache)
    assert db.named == [] and db.log == []


def test_client_logged_in_as_someone_else_is_stopped(make_cache):
    cache, db = make_cache("primary", {"primary": PRIMARY}, client_user_id=SECONDARY)
    read(cache)  # cached reads before the client opens touch only the bound collection

    async def open_client():
        async with cache._telethon_client_cm:
            raise AssertionError("the mismatched client must not be handed out")

    with pytest.raises(AccountMismatch):
        run(open_client())
    assert {name for name, _ in db.log} == {f"messages_user_{PRIMARY}"}


def test_index_creation_goes_to_the_bound_collection_only(make_cache):
    cache, db = make_cache("secondary", {"primary": PRIMARY, "secondary": SECONDARY}, client_user_id=SECONDARY,
                           env_user_id=PRIMARY)
    run(cache.init_messages_collection())
    assert ("messages_user_222", "index") in db.log
    assert all(name == "messages_user_222" for name, _ in db.log)


def test_bad_account_id_in_config_is_rejected(tmp_path, monkeypatch):
    conf = tmp_path / "telegram.toml"
    conf.write_text('[accounts]\nprimary = "111"\n')
    monkeypatch.setenv(tg_config.ENV_VAR, str(conf))
    tg_config._load.cache_clear()
    with pytest.raises(ValueError):
        tg_config.get_config()
    tg_config._load.cache_clear()
