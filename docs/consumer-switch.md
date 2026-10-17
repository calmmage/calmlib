# Telegram consumer follow-up

Prepared 17 Oct 2026 against PR [calmlib#14](https://github.com/calmmage/calmlib/pull/14),
head `5f1eff9a46ab4cdf5f5d53ad1194905e5e12687f`. The PR is open. This worktree only adds
the follow-up patch and verification artifacts; the PR branch and live consumers are unchanged.

Petr's next step: **merge PR 14**. Applying the consumer switch is subsequent work after
the merge, with separate authorization to change the live consumers.

## Patch

[`consumer-switch.patch`](consumer-switch.patch) uses paths relative to `~/calm` and changes ten files:

- PA `project_cache.py` delegates JSONL reading/resume and exported integer conversion to
  `calmlib.telegram.archive`. PA keeps its scope grants, SQLite projection, cursor keys,
  explicit archive-root override, message provenance and local media-copy policy.
- PA `telegram_folder.py` delegates the existing Projects folder update to
  `folders.upsert_folder`. It keeps the primary account, JSON result keys and the existing
  permission to start missing bot dialogs (`start_bots=True`).
- `p-telegram-bots/telegram_bots/registry.py` becomes a compatibility adapter for the shared
  registry. It preserves the project's default registry path and the `TODAY` API.
  `bot_index_report.py` reads through `store.messages_collection("primary")` and
  `chat_id_filter`, and uses the current Calm contact-index path.
- The bot project's `pyproject.toml` and regenerated `uv.lock` pin the exact PR head.
  Explicit `httpx`, `pydantic-settings` and `pymongo` dependencies cover package imports
  and Mongo reads that calmlib's base metadata does not fully declare.
- `telegram-personal` gets the shared APIs and Calm runtime instructions in `SKILL.md`,
  `references/gotchas.md` and `references/recipes.md`. Its contact-index builder derives
  the default source from the configured primary-account id and cache directory.
  Explicit `--source` continues to work without calmlib. The skill was not deployed.

The bot token resolver and disposable token store are outside this switch. Their existing
key-scope policy and storage behavior are preserved. The patch contains no machine config
or token values.

## Verification

Run from this worktree:

```sh
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/petrlavrov/calm/framework/tools/calm-env/.venv/bin/python -m pytest -q -p no:cacheprovider calmlib/telegram/tests
PYTHONPATH="$PWD" /Users/petrlavrov/calm/framework/tools/calm-env/.venv/bin/python -B docs/verify-consumer-switch.py --clean-env
```

- Telegram suite: **41 passed**, one existing Pydantic deprecation warning, 5.68 seconds.
- Patch: `git apply --check` and application succeeded inside a temporary tree.
- Existing PA scope/cursor/runtime tests and bot tests against patched copies:
  **17 passed**, one Pydantic warning.
- Adapter checks passed for the folder output, registry claim/history round-trip,
  account-bound bot report and configured contact-index source.
- A fresh bot virtualenv installed from the patched lockfile and imported the four
  shared APIs and registry adapter successfully.
- All ten live source SHA256s matched before and after verification.

Logs: [`verification/telegram-pytest.log`](verification/telegram-pytest.log) and
[`verification/consumer-switch.log`](verification/consumer-switch.log), with the final
strict patch-whitespace check in [`verification/consumer-switch-final.log`](verification/consumer-switch-final.log).
The broad calmlib suite and live consumer activation were not run; no whole-repository
green or deployed-consumer claim is made.

## Task report

The authorized `dispatch.py say` and `done` commands returned Telegram message ids **15**
and **16**. Notion read-back through an exact-title data-source query confirms status `done`
and the full outcome with the PR link (the direct page GET reset its connection).
Refreshing the existing Telegram task card returned HTTP 404; `dispatch.py` then sent the
separate completion message successfully. The old card refresh remains unverified.
Receipts: `verification/dispatch-say.log`, `verification/dispatch-done.log` and
`verification/notion-readback.json`. Exact command arguments are in `dispatch-commands.json`.

## Later application

After merge and authorization, the next worker should review current consumer changes
and check [`consumer-switch-bases.json`](consumer-switch-bases.json) before applying.
The verification script refuses source drift. Apply the patch from `~/calm`, install the
pinned library in the PA runtime environment, then sync the bot project from the patched
lockfile. A squash merge may require updating the dependency pin to the resulting main
commit and regenerating the lock in an isolated tree.

The machine's existing `CALMLIB_TELEGRAM_CONFIG` must still point at its actual accounts,
cache, archive and registry. No config or data migration is included. Restarting a runtime,
running the live folder updater and deploying the changed skill remain future actions.
