"""tgl status: offline, never hangs, reads only counts and file ages."""

import datetime as dt
import json

import pytest

from calmlib.telegram import config as tg_config
from calmlib.telegram import status as st


@pytest.fixture
def setup(tmp_path, monkeypatch):
    files = tmp_path / "files" / "111"
    files.mkdir(parents=True)
    (files / "dialog_entities.json").write_text(json.dumps([{"id": 1}, {"id": 2}, {"id": 3}]))
    (files / "dialog_filters.json").write_text(json.dumps({"_": "DialogFilters", "filters": [
        {"_": "DialogFilterDefault"},
        {"_": "DialogFilter", "title": {"_": "TextWithEntities", "text": "Work", "entities": []}},
        {"_": "DialogFilter", "title": "Old style"},
    ]}))
    archive = tmp_path / "archive"
    (archive / "primary").mkdir(parents=True)
    registry = tmp_path / "registry.yaml"
    registry.write_text("bots:\n  a_bot: {status: free}\n  b_bot: {status: busy}\n  c_bot: {status: free}\n")
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "primary.session").write_bytes(b"")
    (sessions / "primary.session").chmod(0o644)
    conf = tmp_path / "telegram.toml"
    conf.write_text(
        "[accounts]\nprimary = 111\n"
        # port 1 refuses at once: Mongo down must be a line, not an exception
        f'[cache]\nmongo = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=300"\nfiles = "{tmp_path / "files"}"\n'
        f'[archive]\nroot = "{archive}"\n[bots]\nregistry = "{registry}"\n'
    )
    monkeypatch.setenv(tg_config.ENV_VAR, str(conf))
    monkeypatch.setattr(st, "SESSIONS_DIR", sessions)
    tg_config._load.cache_clear()
    yield
    tg_config._load.cache_clear()


def test_status_reads_side_files_archive_and_bots_with_mongo_down(setup):
    status = st.collect()
    primary = next(a for a in status.accounts if a.account == "primary")
    assert primary.user_id == 111
    assert primary.files.chats == 3
    assert primary.folders.count == 2 and primary.folders.names == ["Work", "Old style"]
    assert primary.archive.ok
    assert not primary.cache.ok and primary.cache.note.startswith("Mongo:")
    assert status.bots.count == 3 and status.bots.names == ["2 free", "1 busy"]
    assert any("session file readable by others" in w for w in status.warnings)
    assert any(w.startswith("Mongo:") for w in status.warnings)


def test_unknown_account_names_nothing(setup):
    status = st.collect()
    service = next(a for a in status.accounts if a.account == "service")
    assert service.user_id is None and not service.cache.ok and not service.files.ok


def test_json_view_is_serializable(setup):
    json.dumps(st.as_dict(st.collect()))


def test_age_labels():
    now = dt.datetime(2026, 10, 16, 12, tzinfo=dt.timezone.utc)
    assert st.age(now - dt.timedelta(minutes=5), now) == "5 min"
    assert st.age(now - dt.timedelta(hours=23), now) == "23 h"
    assert st.age(now - dt.timedelta(days=4), now) == "4 d"
