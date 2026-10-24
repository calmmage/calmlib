"""store, archive, folders, media, bots: offline, against temp files shaped like the real ones."""

import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest

from calmlib.telegram import archive, bots, folders, media, store
from calmlib.telegram import config as tg_config
from calmlib.telegram.config import AccountNotBound

CHAT = -1001234567890


@pytest.fixture
def lib(tmp_path, monkeypatch):
    root, state, files = tmp_path / "nas", tmp_path / "state", tmp_path / "files"
    chat_dir = root / "primary" / f"{CHAT}__Some chat"
    (chat_dir / "media" / "2026").mkdir(parents=True)
    photo = chat_dir / "media" / "2026" / "7_photo.jpg"
    photo.write_bytes(b"jpg")
    (chat_dir / "messages.jsonl").write_text(
        json.dumps({"id": 7, "chat_id": {"low": 1, "high": 0}}) + "\n" + json.dumps({"id": 8}) + "\n" + '{"id": 9'
    )
    state.mkdir()
    db = sqlite3.connect(state / "primary.sqlite")
    db.executescript("""
        create table chats(id integer primary key, title text, kind text, dir text, messages_n integer,
                           history_complete integer);
        create table media(id text primary key, chat_id integer, msg_id integer, kind text, bytes integer,
                           status text, path text);
        create table runs(finished_at text, ok integer);
    """)
    db.execute("insert into chats values(?,?,?,?,?,?)", (CHAT, "Some chat", "group", chat_dir.name, 3, 1))
    db.execute("insert into media values('a',?,7,'photo',3,'done',?)", (CHAT, str(photo)))
    db.execute("insert into media values('b',?,8,'video',null,'pending',null)", (CHAT,))
    db.execute("insert into runs values('2026-10-12T02:15:12+00:00', 1)")
    db.commit()
    db.close()
    (files / "111").mkdir(parents=True)
    (files / "111" / "dialog_filters.json").write_text(json.dumps({"_": "DialogFilters", "filters": [
        {"_": "DialogFilterDefault"},
        {"_": "DialogFilter", "id": 2, "title": {"_": "TextWithEntities", "text": "Work"}, "emoticon": "💼",
         "pinned_peers": [{}], "include_peers": [{}, {}], "exclude_peers": []},
    ]}))
    registry = tmp_path / "registry.yaml"
    registry.write_text(
        "version: 2\naccounts:\n  primary: {bot_cap: 20}\nbots:\n"
        "- {username: a_bot, owner_account: primary, status: busy, token_key: A_BOT_TOKEN,"
        " consumers: [{project: x}]}\n"
        "- {username: b_bot, owner_account: primary, status: free, token_key_aliases: [B_OLD]}\n"
        "- {username: c_bot, owner_account: primary, status: deleted}\n"
    )
    conf = tmp_path / "telegram.toml"
    conf.write_text(f'[accounts]\nprimary = 111\n[cache]\nfiles = "{files}"\n'
                    f'[archive]\nroot = "{root}"\nstate = "{state}"\n[bots]\nregistry = "{registry}"\n')
    monkeypatch.setenv(tg_config.ENV_VAR, str(conf))
    tg_config._load.cache_clear()
    yield SimpleNamespace(root=root, state=state, files=files, photo=photo, chat_dir=chat_dir, registry=registry)
    tg_config._load.cache_clear()


# store ------------------------------------------------------------------------------------------

def test_collection_comes_from_the_account_map_only(lib):
    class Client(dict):
        def __missing__(self, db):
            return {"messages_user_111": f"{db}/messages_user_111"}

    assert store.messages_collection("primary", client=Client()) == "telegram_cache/messages_user_111"
    with pytest.raises(AccountNotBound):
        store.messages_collection("secondary", client=Client())


@pytest.mark.parametrize("bad", [0, -5, "111", True, None])
def test_collection_name_refuses_anything_but_a_user_id(bad):
    with pytest.raises(AccountNotBound):
        store.collection_name(bad)


def test_chat_filter_matches_int_and_str_rows():
    assert store.chat_id_filter([5]) == {"chat_id": {"$in": [5, "5"]}}


# archive ----------------------------------------------------------------------------------------

def test_archive_reads_complete_lines_and_resumes(lib):
    rows = list(archive.messages("primary", CHAT))
    assert [r["id"] for r, _ in rows] == [7, 8]  # the half-written line 9 waits for the next read
    offset = rows[0][1]
    assert [r["id"] for r, _ in archive.messages("primary", CHAT, offset)] == [8]
    assert archive.to_int(rows[0][0]["chat_id"]) == 1


def test_archive_restarts_when_the_file_shrank(lib):
    assert [r["id"] for r, _ in archive.messages("primary", CHAT, offset=10**9)] == [7, 8]


def test_archive_index_and_summary(lib):
    assert archive.chat_dir("primary", CHAT) == lib.chat_dir
    assert [c.title for c in archive.chats("primary")] == ["Some chat"]
    info = archive.summary("primary")
    assert info["chats"] == 1 and info["messages"] == 3 and info["media"] == {"done": 1, "pending": 1}


def test_archive_unmounted_is_a_clear_error(lib, tmp_path, monkeypatch):
    conf = tmp_path / "other.toml"
    conf.write_text(f'[archive]\nroot = "{tmp_path / "gone"}"\n')
    monkeypatch.setenv(tg_config.ENV_VAR, str(conf))
    with pytest.raises(archive.ArchiveUnavailable):
        archive.account_root("primary")


# media ------------------------------------------------------------------------------------------

def test_media_prefers_the_archive_and_never_downloads_without_a_client(lib):
    assert media.archived_file("primary", CHAT, 7) == lib.photo
    assert media.archived_file("primary", CHAT, 8) is None  # pending in the exporter
    assert asyncio.run(media.get_file("primary", CHAT, 8)) is None


def test_media_download_goes_to_the_side_cache(lib):
    class Client:
        async def get_messages(self, chat, ids):
            return SimpleNamespace(media=True, file=SimpleNamespace(name="clip.mp4", ext=".mp4"))

        async def download_media(self, message, file):
            open(file, "wb").write(b"mp4")
            return file

    path = asyncio.run(media.get_file("primary", CHAT, 8, client=Client()))
    assert path == lib.files / "111" / "media" / str(CHAT) / "8_clip.mp4" and path.read_bytes() == b"mp4"
    assert media.downloaded_file("primary", CHAT, 8) == path
    assert not list(lib.chat_dir.rglob("8_*"))  # the archive is the exporter's, never written here


# folders ----------------------------------------------------------------------------------------

def test_cached_folders_skip_the_default_and_read_new_titles(lib):
    assert folders.cached_folders(111) == [folders.Folder(id=2, title="Work", emoticon="💼", chats=3, excluded=0)]
    assert folders.cached_folders(999) == []


def test_upsert_folder_updates_by_title_and_starts_bots_only_when_asked(lib):
    from telethon.tl.types import DialogFilter, DialogFilterDefault, TextWithEntities

    sent, updates = [], []

    class Client:
        async def get_dialogs(self, limit=None):
            return [SimpleNamespace(id=1)]

        async def get_entity(self, ref):
            return SimpleNamespace(id={"old_bot": 1, "new_bot": 2}[ref])

        async def get_input_entity(self, ref):
            if ref == "missing":
                raise ValueError(ref)
            return f"peer:{getattr(ref, 'id', ref)}"

        async def send_message(self, entity, text):
            sent.append((entity.id, text))

        async def __call__(self, request):
            if type(request).__name__ == "GetDialogFiltersRequest":
                existing = DialogFilter(id=4, title=TextWithEntities("Projects", []), pinned_peers=[],
                                        include_peers=[], exclude_peers=[])
                return SimpleNamespace(filters=[DialogFilterDefault(), existing])
            updates.append(request)

    out = asyncio.run(folders.upsert_folder(Client(), "Projects", bots=["old_bot", "new_bot"],
                                            chats=[-100, "missing"]))
    assert out["id"] == 4 and out["updated_existing"] and out["bots_not_started"] == ["new_bot"]
    assert out["chats_not_found"] == ["missing"] and sent == []
    assert updates[0].filter.include_peers == ["peer:1", "peer:-100"]

    out = asyncio.run(folders.upsert_folder(Client(), "Projects", bots=["new_bot"], start_bots=True))
    assert sent == [(2, "/start")] and out["bots"] == 1


# bots -------------------------------------------------------------------------------------------

def test_registry_load_get_quota(lib):
    reg = bots.Registry.load()
    assert reg.get("@A_BOT").username == "a_bot" and reg.get("A_BOT_TOKEN").username == "a_bot"
    assert reg.get("b_old").username == "b_bot"
    assert reg.quota("primary") == (2, 20)
    assert [b.username for b in reg.free()] == ["b_bot"]


def test_registry_round_trips_without_losing_claims(lib):
    bots.Registry.load().save()
    text = lib.registry.read_text()
    assert text.startswith(bots.HEADER) and "token:" not in text
    assert bots.Registry.load().get("a_bot").consumers[0].project == "x"


def test_bot_token_resolves_by_key_name_only(lib):
    asked = []

    def resolve(name):
        asked.append(name)
        return {"B_OLD": "secret"}.get(name)

    assert bots.bot_token("b_bot", resolve=resolve) == "secret" and asked == ["B_OLD"]
    assert bots.bot_token("c_bot", resolve=resolve) is None
    with pytest.raises(KeyError):
        bots.bot_token("nobody_bot", resolve=resolve)
