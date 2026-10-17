#!/usr/bin/env python3
"""Check the saved patch using temporary copies; never patch a live consumer."""
import argparse
import asyncio
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import AsyncMock, patch

DOCS = Path(__file__).resolve().parent
LIBRARY = DOCS.parent
CALM = Path.home() / "calm"
BASES = json.loads((DOCS / "consumer-switch-bases.json").read_text())


def source_hashes():
    return {rel: hashlib.sha256((CALM / rel).read_bytes()).hexdigest() for rel in BASES}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(cmd, cwd, env):
    print("$ " + " ".join(map(str, cmd)), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True, timeout=120)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-env", action="store_true", help="also install the pinned bot environment in the temporary tree")
    args = parser.parse_args()
    before = source_hashes()
    if before != BASES:
        raise SystemExit("Consumer files changed since preparation; review/rebase the patch first")
    with tempfile.TemporaryDirectory(prefix="calmlib-consumer-check-") as folder:
        stage = Path(folder)
        for rel in BASES:
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(CALM / rel, target)
        # Unchanged modules needed by the existing tests. No runtime state or registry is copied.
        for project, subdir in (("p-personal-assistant", ""), ("p-telegram-bots", "telegram_bots")):
            for source in (CALM / "projects" / project / subdir).glob("*.py"):
                target = stage / source.relative_to(CALM)
                if not target.exists():
                    shutil.copyfile(source, target)
        shutil.copyfile(CALM / "projects/p-telegram-bots/ingest.example.yaml",
                        stage / "projects/p-telegram-bots/ingest.example.yaml")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        run(["git", "apply", "--whitespace=error", "--check", DOCS / "consumer-switch.patch"], stage, env)
        run(["git", "apply", DOCS / "consumer-switch.patch"], stage, env)
        print("patch applicability: OK (10 files, temporary tree)", flush=True)
        for rel in BASES:
            if rel.endswith(".py"):
                compile((stage / rel).read_text(), rel, "exec")
        pa = stage / "projects/p-personal-assistant"
        bot = stage / "projects/p-telegram-bots"
        if args.clean_env:
            run(["uv", "run", "--directory", bot, "--frozen", "--no-dev", "python", "-B", "-c",
                 "from calmlib.telegram import archive, folders, bots, store; "
                 "from telegram_bots.registry import Registry; print('clean consumer imports: OK')"], stage, env)
        env["PYTHONPATH"] = os.pathsep.join(map(str, [pa, bot, LIBRARY, CALM / "framework/tools/vault"]))
        env["CALM_PROJECT_ASSISTANT_STATE_DIR"] = str(stage / "pa-state")
        (stage / "pa-state").mkdir()
        run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--import-mode=importlib",
             CALM / "projects/p-personal-assistant/test_project_bots.py",
             CALM / "projects/p-telegram-bots/tests"], stage, env)
        sys.path[:0] = [str(pa), str(bot), str(LIBRARY)]

        # Keep the Projects folder's output contract and its existing /start policy.
        mod = load("consumer_folder", pa / "telegram_folder.py")
        fake_client = object()

        class Lease:
            async def __aenter__(self):
                return fake_client

            async def __aexit__(self, *args):
                pass

        shared_result = dict(folder="Projects", id=4, bots=1, chats=1, chats_not_found=[-99],
                             bots_not_started=[], updated_existing=True)
        shared_upsert = AsyncMock(return_value=shared_result)
        output = io.StringIO()
        with patch.object(mod, "wanted", return_value=(["fixture_bot"], [-1, -99])), \
             patch.object(mod, "get_telethon_client_context", return_value=Lease()) as lease, \
             patch.object(mod, "upsert_folder", shared_upsert), contextlib.redirect_stdout(output):
            asyncio.run(mod.main())
        lease.assert_called_once_with(account="primary")
        shared_upsert.assert_awaited_once_with(fake_client, "Projects", bots=["fixture_bot"],
                                              chats=[-1, -99], emoticon="🤖", start_bots=True)
        assert json.loads(output.getvalue()) == dict(folder="Projects", id=4, bots=1, groups=1,
                                                     groups_not_found=[-99], updated_existing=True)

        # The compatibility registry still round-trips consumers and history to an explicit file.
        from telegram_bots.registry import Bot, Consumer, Registry
        path = stage / "registry.yaml"
        reg = Registry(accounts={"primary": {"bot_cap": 20}}, bots=[Bot(
            username="fixture_bot", consumers=[Consumer(project="fixture")], history=[{"released": "fixture"}])])
        reg.save(path)
        restored = Registry.load(path)
        assert isinstance(restored, Registry)
        assert restored.get("@fixture_bot").consumers[0].project == "fixture"
        assert restored.get("fixture_bot").history == [{"released": "fixture"}]

        # A bot report uses the account-bound collection and still accepts old string chat ids.
        report = load("consumer_bot_report", bot / "scripts/bot_index_report.py")
        contact_index = stage / "contacts-fixture.tsv"
        contact_index.write_text("7\tfixture_bot\tFixture\tbot\tfalse\tfalse\tfalse\n")
        collection = type("Collection", (), {"find": lambda self, query: [
            dict(chat_id="7", id="1", date="2026-10-01T00:00:00+00:00", out="True", message="fixture")
        ] if query == {"chat_id": {"$in": [7, "7"]}} else []})()
        from calmlib.telegram import store
        with patch.object(report, "CONTACT_INDEX", contact_index), patch.object(report, "ROOT", stage), \
             patch.object(store, "messages_collection", return_value=collection) as collection_for:
            rows, identities = report.load_cache()
        collection_for.assert_called_once_with("primary")
        assert rows[0]["messages"] == rows[0]["mine"] == 1
        assert identities["fixture_bot"]["consumers"][0]["project"] == "fixture"

        # The contact builder derives the source from the configured account, with no Telegram call.
        builder = load("consumer_contacts", stage / "skills/library/ecosystem/telegram-personal/scripts/build_primary_contact_index.py")
        from calmlib.telegram import config
        conf = stage / "telegram.toml"
        conf.write_text(f'[accounts]\nprimary = 111\n[cache]\nfiles = "{stage / "cache"}"\n')
        with patch.dict(os.environ, {"CALMLIB_TELEGRAM_CONFIG": str(conf)}):
            source = builder.default_source()
            assert source == stage / "cache/111/dialog_entities.json"
            source.parent.mkdir(parents=True)
            source.write_text(json.dumps([dict(_="User", id=7, first_name="Fixture", bot=True)]))
            assert builder.build(source, stage / "contacts.tsv") == 1
            assert "7\t\tFixture\tbot" in (stage / "contacts.tsv").read_text()
        config._load.cache_clear()
        print("folder adapter, registry round-trip, account-bound bot report, configured contact source: OK", flush=True)
    assert source_hashes() == before
    print("live consumer SHA256s unchanged: OK", flush=True)


if __name__ == "__main__":
    main()
