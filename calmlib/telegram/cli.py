"""tgl: local Telegram on this machine.

    tgl status                  what each account has: session, cache, chats, folders, archive, bots
    tgl status --json           the same for scripts and agents
    tgl folders [-a ACCOUNT]    folders as last cached
    tgl archive [-a ACCOUNT]    archived chats, largest first
    tgl media CHAT MSG          where a message's file is (archive, earlier download)
    tgl bots [--status S]       the bot registry

Offline: no Telegram network, no message text. (Named tgl because `tg` is a common alias.)
"""

from __future__ import annotations

import argparse
import json
import sys

from calmlib.telegram import status as st


def _cell(src: st.Source, now, what: str) -> str:
    if not src.ok:
        return f"[dim]{src.note or '—'}[/dim]"
    when = st.age(src.newest, now)
    if what == "cache":
        return f"{src.count:,} msgs · {src.chats:,} chats · {when}"
    if what == "files":
        return f"{src.chats:,} chats · {when}"
    if what == "folders":
        named = [n for n in src.names if any(ch.isalnum() for ch in n)]  # skip "-----" dividers
        more = f" +{len(named) - 3}" if len(named) > 3 else ""
        return f"{src.count} · {', '.join(named[:3])}{more} · {when}"
    if what == "archive" and src.count is not None:
        saved = next((n.split()[0] for n in src.names if n.endswith(" done")), "0")
        return f"{src.count:,} msgs · {src.chats:,} chats · {int(saved):,} files · {when}"
    if what == "session":
        warn = f" · [red]{src.note}[/red]" if src.note else ""
        return f"yes · {when}{warn}"
    return f"yes · {when}" if when else "yes"


def _print(status: st.Status, console=None) -> None:
    from rich.console import Console
    from rich.table import Table

    now = None
    console = console or Console()
    table = Table(title=f"Local Telegram · {st.host()}", title_justify="left", box=None, pad_edge=False,
                  header_style="bold", padding=(0, 2, 0, 0))
    table.add_column("")
    for a in status.accounts:
        table.add_column(a.account)
    rows = [
        ("user id", lambda a: str(a.user_id) if a.user_id else "[dim]—[/dim]"),
        ("session", lambda a: _cell(a.session, now, "session")),
        ("cache", lambda a: _cell(a.cache, now, "cache")),
        ("dialogs", lambda a: _cell(a.files, now, "files")),
        ("folders", lambda a: _cell(a.folders, now, "folders")),
        ("archive", lambda a: _cell(a.archive, now, "archive")),
    ]
    for label, cell in rows:
        table.add_row(f"[bold]{label}[/bold]", *(cell(a) for a in status.accounts))
    console.print(table)

    bots = status.bots
    line = f"{bots.count} in registry · " + ", ".join(bots.names) if bots.ok else f"[dim]{bots.note}[/dim]"
    console.print(f"\n[bold]bots[/bold]     {line}")
    console.print(f"[bold]config[/bold]   {status.config.path or '[dim]none (defaults)[/dim]'}")
    for w in status.warnings:
        console.print(f"[yellow]![/yellow] {w}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tgl", description="Local Telegram on this machine.")
    sub = parser.add_subparsers(dest="command", required=True)
    p_status = sub.add_parser("status", help="what each account has here (offline)")
    p_status.add_argument("--json", action="store_true", help="machine-readable output")
    for name, text in (("folders", "folders as last cached (offline)"), ("archive", "archived chats, largest first")):
        p = sub.add_parser(name, help=text)
        p.add_argument("-a", "--account", default="primary")
        if name == "archive":
            p.add_argument("-n", "--limit", type=int, default=20)
    p_media = sub.add_parser("media", help="where a message's file is")
    p_media.add_argument("chat", type=int)
    p_media.add_argument("message", type=int)
    p_media.add_argument("-a", "--account", default="primary")
    p_bots = sub.add_parser("bots", help="the bot registry")
    p_bots.add_argument("--status", choices=["free", "busy", "keep", "deleted", "foreign"])
    args = parser.parse_args(argv)

    if args.command == "folders":
        from calmlib.telegram.folders import cached_folders
        from calmlib.telegram.store import account_user_id

        for f in cached_folders(account_user_id(args.account)):
            print(f"{f.id:>3}  {f.emoticon or ' '}  {f.title:30} {f.chats:>4} chats")
        return 0
    if args.command == "archive":
        from calmlib.telegram import archive

        rows = archive.chats(args.account)
        for c in rows[: args.limit]:
            print(f"{c.chat_id:>15}  {c.kind:8} {c.messages:>9,}  {'' if c.complete else '(partial) '}{c.title}")
        print(f"{len(rows):,} chats · {sum(c.messages for c in rows):,} messages")
        return 0
    if args.command == "media":
        from calmlib.telegram import media

        path = media.archived_file(args.account, args.chat, args.message) or media.downloaded_file(
            args.account, args.chat, args.message)
        print(path or "not saved here (the archive exporter or `media.get_file(..., client=...)` can fetch it)")
        return 0 if path else 1
    if args.command == "bots":
        from calmlib.telegram.bots import Registry

        reg = Registry.load()
        for b in sorted(reg.bots, key=lambda b: (b.status, b.username.lower())):
            if args.status and b.status != args.status:
                continue
            who = ", ".join(c.project for c in b.consumers) or "-"
            print(f"{b.status:8} {b.owner_account:9} {b.handle:36} {who}")
        print(f"{len(reg.bots)} bots · " + " · ".join(
            f"{acc} {reg.quota(acc)[0]}/{reg.quota(acc)[1]}" for acc in reg.accounts))
        return 0

    if args.command == "status":
        status = st.collect()
        if args.json:
            json.dump(st.as_dict(status), sys.stdout, indent=2, ensure_ascii=False)
            print()
        else:
            _print(status)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
