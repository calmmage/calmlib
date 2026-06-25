"""Patchbay CLI — query, navigate, and manage AI sessions."""

from collections import OrderedDict
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Patchbay — AI session coordinator")
console = Console()


@app.command()
def search(
    query: str,
    limit: int = typer.Option(10, "-n", "--limit"),
    all_sources: bool = typer.Option(False, "--all", help="Include AI-created sessions"),
):
    """Search sessions by keyword across title, topics, first message."""
    from calmlib.utils.patchbay import search_sessions

    sessions = search_sessions(query, human_only=not all_sources, limit=limit)
    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return
    for s in sessions:
        console.print(s.summary())
        console.print()


@app.command()
def find(
    query: str,
    limit: int = typer.Option(10, "-n", "--limit"),
    depth: int = typer.Option(None, "-d", "--depth", help="Days back (default: all time)"),
    all_sources: bool = typer.Option(False, "--all", help="Include AI-created sessions"),
):
    """Semantic search over session content (via textvault embeddings)."""
    from datetime import timezone
    from calmlib.utils.patchbay import semantic_search_sessions

    since = None
    if depth is not None:
        since = datetime.now(timezone.utc) - timedelta(days=depth)

    results = semantic_search_sessions(
        query, limit=limit, human_only=not all_sources, since=since,
    )
    if not results:
        console.print("[dim]No sessions found.[/dim]")
        return
    for r in results:
        s = r["session"]
        sim = r["sim"]
        matches = r["matches"]
        console.print(
            f"[dim]{sim:.2f}[/dim]  [cyan]{s.session_id[:12]}[/cyan]  "
            f"[magenta]{s.title or '(no title)'}[/magenta]  "
            f"[dim]({matches} turn{'s' if matches != 1 else ''})[/dim]"
        )
        if s.topics_short:
            console.print(f"        [dim]topics:[/dim] {s.topics_short}")
        if r["preview"]:
            console.print(f"        [dim]↳ {r['preview']}[/dim]")
        console.print()


@app.command("list")
def list_cmd(
    limit: int = typer.Option(10, "-n", "--limit"),
    since: str = typer.Option(None, "--since", help="e.g. 3d, 12h, 1w"),
    status: str = typer.Option(None, "--status"),
    all_sources: bool = typer.Option(False, "--all", help="Include AI-created sessions"),
):
    """List recent sessions."""
    from calmlib.utils.patchbay import count_sessions, list_sessions

    since_dt = None
    if since:
        since_dt = _parse_since(since)

    sessions = list_sessions(
        human_only=not all_sources, limit=limit, since=since_dt, status=status
    )
    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    # -- Group sessions by date, then render with swimlane separators --
    groups = _group_sessions_by_date(sessions)

    table = Table(show_header=True, show_lines=False)
    table.add_column("ID", width=14)
    table.add_column("Session", min_width=30)
    table.add_column("Project", max_width=20)

    first_group = True
    for group_label, group_sessions in groups.items():
        if not first_group:
            table.add_section()
        first_group = False

        count_suffix = f"  [dim]({len(group_sessions)})[/dim]" if len(group_sessions) > 1 else ""
        table.add_row(
            f"[bold cyan]── {group_label}{count_suffix}[/bold cyan]",
            "", "",
        )

        group_sessions.sort(key=lambda s: s.timestamp or datetime.min)

        for s in group_sessions:
            # ID + time
            time_str = _format_time(s.timestamp) if s.timestamp else ""
            id_cell = f"{s.session_id[:12]}\n[dim]{time_str}[/dim]"

            # Title + metadata suffix + topics
            title = s.title or "(no title)"
            # Status/wrapup indicators
            if s.status == "done" and s.wrapup_doc:
                title = f"[dim strikethrough]{title}[/dim strikethrough] [green]wrapped[/green]"
            elif s.status == "done":
                title = f"[dim strikethrough]{title}[/dim strikethrough]"
            elif s.wrapup_doc:
                title = f"{title} [green]wrapped[/green]"
            meta_parts = []
            if s.message_count:
                meta_parts.append(f"{s.message_count} msgs")
            if s.source and s.source != "human":
                meta_parts.append(s.source)
            meta_suffix = f" [dim]({', '.join(meta_parts)})[/dim]" if meta_parts else ""
            topics_line = f"\n[dim]{s.topics_short}[/dim]" if s.topics_short else ""
            title_cell = f"{title}{meta_suffix}{topics_line}"

            # Project/task
            project_cell = s.project or ""
            if s.task and s.task != s.project:
                project_cell += f"\n[dim]{s.task}[/dim]" if project_cell else s.task

            table.add_row(id_cell, title_cell, project_cell)

    console.print(table)

    total = count_sessions(
        human_only=not all_sources, since=since_dt, status=status
    )
    console.print(f"[dim]Total: {total} sessions (showing {len(sessions)})[/dim]")


@app.command()
def summary(session_id: str):
    """Show detailed summary for a session."""
    from calmlib.utils.patchbay import get_session_summary

    text = get_session_summary(session_id, refresh_metadata=True)
    if not text:
        console.print(f"[red]Session {session_id} not found.[/red]")
        raise typer.Exit(1)
    console.print(text)


@app.command("refresh")
def refresh_cmd(
    limit: int = typer.Option(20, "-n", "--limit", help="Max sessions to refresh"),
    since: int = typer.Option(24, "--since", help="Hours to look back"),
    all_sources: bool = typer.Option(False, "--all", help="Include AI-created sessions"),
):
    """Bulk-refresh titles for recent sessions from Claude JSONL files."""
    from calmlib.utils.patchbay.query import bulk_refresh_metadata

    sessions = bulk_refresh_metadata(
        limit=limit,
        since_hours=since,
        human_only=not all_sources,
    )
    if not sessions:
        console.print("[dim]No sessions refreshed.[/dim]")
        return
    console.print(f"Refreshed {len(sessions)} sessions:")
    for s in sessions:
        title = s.title or "(no title)"
        console.print(f"  {s.session_id[:12]}  {title}")


@app.command("rename")
def rename_cmd(
    session_id: str,
    title: str = typer.Argument(None, help="Title text. Omit to auto-generate."),
    style: bool = typer.Option(False, "--style", "-s", help="Generate a styled title via LLM"),
):
    """Set a human title for a session. Use --style to auto-generate with varied formatting."""
    from calmlib.utils.patchbay import get_session, set_session_title

    if style or title is None:
        session = get_session(session_id)
        if not session:
            console.print(f"[red]Session {session_id} not found.[/red]")
            raise typer.Exit(1)
        description = session.first_message or session.title or session.session_id
        from calmlib.utils.patchbay.title_style import generate_styled_title
        title = generate_styled_title(description)
        console.print(f"[dim]Generated:[/dim] {title}")

    session = set_session_title(session_id, title)
    if not session:
        console.print(f"[red]Session {session_id} not found.[/red]")
        raise typer.Exit(1)
    console.print(f"Renamed {session.session_id[:12]} → {session.title}")


@app.command()
def link(
    session_id: str,
    project: str = typer.Option(None, "--project", "-p"),
    task: str = typer.Option(None, "--task", "-t"),
    task_id: str = typer.Option(None, "--task-id", help="Stable mainline task id."),
):
    """Link a session to a project and/or task."""
    from calmlib.utils.patchbay import link_session

    if not project and not task and not task_id:
        console.print("[red]Provide --project, --task, and/or --task-id.[/red]")
        raise typer.Exit(1)
    ok = link_session(session_id, project=project, task=task, task_id=task_id)
    if ok:
        console.print(
            f"Linked {session_id[:12]} → "
            f"project={project}, task={task}, task_id={task_id}"
        )
    else:
        console.print(f"[red]Session {session_id} not found.[/red]")


@app.command()
def tag(session_id: str, tags: list[str]):
    """Add tags to a session."""
    from calmlib.utils.patchbay import tag_session

    ok = tag_session(session_id, tags)
    if ok:
        console.print(f"Tagged {session_id[:12]} with {tags}")
    else:
        console.print(f"[red]Session {session_id} not found.[/red]")


@app.command()
def cleanup(
    max_age_hours: int = typer.Option(1, "--max-age", help="Hours before empty sessions are deleted"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute"),
):
    """Delete empty sessions older than max-age hours."""
    from calmlib.utils.patchbay import cleanup_empty_sessions

    count = cleanup_empty_sessions(max_age_hours=max_age_hours, dry_run=dry_run)
    if dry_run:
        console.print(f"[dim]Would delete {count} empty sessions (use --execute to confirm)[/dim]")
    else:
        console.print(f"Deleted {count} empty sessions.")


@app.command("sweep")
def sweep_cmd(
    max_age: int = typer.Option(1, "--max-age", help="Hours before empty sessions are parked"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute"),
    resurrect: bool = typer.Option(True, "--resurrect/--no-resurrect", help="Also check parked sessions for resurrection"),
):
    """Park empty sessions and resurrect ones that gained content."""
    from calmlib.utils.patchbay.query import resurrect_sessions, sweep_empty_sessions

    if resurrect:
        restored = resurrect_sessions()
        if restored:
            console.print(f"[green]Resurrected {restored} sessions[/green]")

    count = sweep_empty_sessions(max_age_hours=max_age, dry_run=dry_run)
    if dry_run:
        console.print(f"[dim]Would park {count} empty sessions (use --execute to confirm)[/dim]")
    else:
        console.print(f"Parked {count} empty sessions.")


@app.command()
def done(
    query: str = typer.Argument(..., help="Session ID (or prefix) or title substring"),
    wrapup: str = typer.Option(None, "--wrapup", "-w", help="Path to wrapup/handoff doc"),
):
    """Mark a session as done (hides from default views). Optionally link a wrapup doc."""
    from calmlib.utils.patchbay import find_session_by_title, get_session, update_session_status

    session = _resolve_session(query)
    if not session:
        console.print(f"[red]Session not found: {query}[/red]")
        raise typer.Exit(1)

    ok = update_session_status(session.session_id, "done", wrapup_doc=wrapup)
    if ok:
        updated_session = get_session(session.session_id, refresh_metadata=False) or session
        msg = f"Done {updated_session.session_id[:12]} — {updated_session.title or '(no title)'}"
        if wrapup:
            msg += f"\n  wrapup: {wrapup}"
        console.print(msg)
    else:
        console.print(f"[red]Failed to update session.[/red]")
        raise typer.Exit(1)


@app.command()
def followup(
    query: str = typer.Argument(..., help="Session ID (or prefix) or title substring"),
    extract: bool = typer.Option(False, "--extract", "-e", help="Extract unfinished items as plaintask tasks"),
    launch: bool = typer.Option(False, "--launch", "-l", help="Launch a new session from the wrapup doc"),
):
    """Show follow-up tasks from a session's wrapup doc, or launch a continuation session."""
    from pathlib import Path

    from calmlib.utils.patchbay import get_session

    session = _resolve_session(query)
    if not session:
        console.print(f"[red]Session not found: {query}[/red]")
        raise typer.Exit(1)

    if not session.wrapup_doc:
        console.print(f"[red]No wrapup doc linked for {session.session_id[:12]}.[/red]")
        console.print("[dim]Use: pb done <session> --wrapup <path>[/dim]")
        raise typer.Exit(1)

    doc_path = Path(session.wrapup_doc).expanduser()
    if not doc_path.exists():
        console.print(f"[red]Wrapup doc not found: {doc_path}[/red]")
        raise typer.Exit(1)

    content = doc_path.read_text()

    # Extract unfinished items (lines starting with "- [ ]" under Unfinished/Handoff)
    items = _extract_handoff_items(content)

    if not extract and not launch:
        # Default: show the unfinished items
        console.print(f"[bold]{session.title or session.session_id[:12]}[/bold]")
        console.print(f"[dim]{session.wrapup_doc}[/dim]\n")
        if items:
            console.print("[bold]Unfinished / Handoff:[/bold]")
            for item in items:
                console.print(f"  - [ ] {item}")
        else:
            console.print("[dim]No unfinished items found.[/dim]")
        return

    if extract:
        if not items:
            console.print("[dim]No unfinished items to extract.[/dim]")
            return
        _extract_to_plaintask(items, session)
        return

    if launch:
        _launch_followup(session, doc_path, items)


def _resolve_session(query: str):
    """Resolve a session by ID prefix, exact title, or regex search (includes done/archived)."""
    from calmlib.utils.patchbay import find_session_by_title, get_session, search_sessions

    session = get_session(query) or find_session_by_title(query)
    if not session:
        matches = search_sessions(query, limit=1, exclude_archived=False, exclude_done=False)
        if matches:
            session = matches[0]
    return session


def _extract_handoff_items(content: str) -> list[str]:
    """Extract checkbox items from the Unfinished/Handoff section of a wrapup doc."""
    lines = content.split("\n")
    in_section = False
    items = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## Unfinished") or stripped.startswith("## Handoff"):
            in_section = True
            continue
        if in_section and stripped.startswith("## "):
            break
        if in_section and stripped.startswith("- [ ]"):
            item = stripped.removeprefix("- [ ]").strip()
            # Strip bold markers
            item = item.replace("**", "")
            items.append(item)
    return items


def _extract_to_plaintask(items: list[str], session):
    """Add unfinished items as plaintask tasks."""
    import subprocess

    project = session.project
    for item in items:
        # Truncate to reasonable title length
        title = item[:80] if len(item) > 80 else item
        cmd = ["uv", "run", "typer", "tools/task_management/plaintask/cli/task_cli.py", "run", "add", item, "--title", title]
        if project:
            cmd.extend(["-p", project])
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True, cwd="/Users/petrlavrov/calmmage")
            console.print(f"  [green]+[/green] {title}")
        except subprocess.CalledProcessError as e:
            console.print(f"  [red]![/red] {title}: {e.stderr.strip()}")
    console.print(f"\n[dim]Extracted {len(items)} tasks{f' to project {project}' if project else ''}[/dim]")


def _launch_followup(session, doc_path, items):
    """Launch a new session with the wrapup doc as context."""
    from calmlib.utils.patchbay import launch_session

    items_text = "\n".join(f"- [ ] {item}" for item in items) if items else "(no specific items)"
    prompt = (
        f"This is a follow-up session continuing from a previous session.\n"
        f"Previous session: {session.title or session.session_id[:12]}\n\n"
        f"Read the wrapup doc at {doc_path} for full context.\n\n"
        f"Unfinished items:\n{items_text}\n\n"
        f"Pick up where we left off — start with the first unfinished item."
    )

    result = launch_session(
        prompt=prompt,
        title=f"Follow-up: {session.title or session.session_id[:12]}"[:60],
        project=session.project,
        task=session.task,
    )
    console.print(f"Launched follow-up: {result['session_id'][:12]}")
    console.print(f"  resume: {result['resume_command']}")


@app.command()
def archive(session_id: str):
    """Archive a session (hides from default views)."""
    from calmlib.utils.patchbay import update_session_status

    ok = update_session_status(session_id, "archived")
    if ok:
        console.print(f"Archived {session_id[:12]}")
    else:
        console.print(f"[red]Session {session_id} not found.[/red]")
        raise typer.Exit(1)


@app.command()
def fav(session_id: str):
    """Mark a session as favorite."""
    from calmlib.utils.patchbay import fav_session

    ok = fav_session(session_id)
    if ok:
        console.print(f"Faved {session_id[:12]} ⭐")
    else:
        console.print(f"[red]Session {session_id} not found.[/red]")
        raise typer.Exit(1)


@app.command()
def unfav(session_id: str):
    """Remove favorite mark from a session."""
    from calmlib.utils.patchbay import unfav_session

    ok = unfav_session(session_id)
    if ok:
        console.print(f"Unfaved {session_id[:12]}")
    else:
        console.print(f"[red]Session {session_id} not found.[/red]")
        raise typer.Exit(1)


@app.command()
def favs(
    limit: int = typer.Option(20, "-n", "--limit"),
):
    """List favorite sessions."""
    from calmlib.utils.patchbay import list_fav_sessions

    sessions = list_fav_sessions(limit=limit)
    if not sessions:
        console.print("[dim]No favorite sessions.[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("ID", width=12)
    table.add_column("Title", max_width=40)
    table.add_column("Topics", max_width=30)
    table.add_column("Time", width=16)

    for s in sessions:
        table.add_row(
            s.session_id[:12],
            s.title or "(no title)",
            (s.topics_short or "")[:30],
            s.timestamp.strftime("%Y-%m-%d %H:%M") if s.timestamp else "",
        )
    console.print(table)


@app.command()
def exists(
    query: str,
    by: str = typer.Option("auto", help="Lookup mode: title, id, or auto (tries id first, then title)"),
):
    """Check if a session exists. Exit 0 = yes (prints session_id), 1 = no."""
    from calmlib.utils.patchbay import find_session_by_title, get_session

    session = None
    if by == "id":
        session = get_session(query)
    elif by == "title":
        session = find_session_by_title(query)
    else:
        session = get_session(query) or find_session_by_title(query)

    if session:
        console.print(session.session_id)
    else:
        raise typer.Exit(1)


@app.command()
def whoami(
    message: str = typer.Argument(None, help="Substring of first user message for better matching"),
):
    """Find the most recent session for this CWD (best guess at current session)."""
    from calmlib.utils.patchbay import bulk_refresh_metadata, find_current_session

    bulk_refresh_metadata(since_hours=48, human_only=True)

    session = find_current_session(first_message_substring=message, refresh_metadata=True)
    if not session:
        console.print("[dim]No session found for this directory.[/dim]")
        raise typer.Exit(1)
    console.print(session.summary())


@app.command("launch")
def launch_cmd(
    prompt: str = typer.Argument(..., help="Initial message for the session"),
    name: str = typer.Option(None, "--name", "-n", help="Human-readable session title"),
    project: str = typer.Option(None, "-p", "--project", help="Link to plaintask project"),
    task: str = typer.Option(None, "-t", "--task", help="Link to plaintask task"),
    client: str = typer.Option("claude", "-c", "--client", help="claude | codex | gemini"),
    model: str = typer.Option(None, "-m", "--model", help="Model override"),
    yolo: bool = typer.Option(False, "--yolo", help="Skip permission checks"),
):
    """Launch a new AI session. Registers in patchbay, prints resume command."""
    from calmlib.utils.patchbay import launch_session

    result = launch_session(
        prompt=prompt,
        title=name,
        project=project,
        task=task,
        client=client,
        model=model,
        dangerously_skip_permissions=yolo,
    )
    console.print(f"✓ {result['title']}")
    console.print(f"  session: {result['session_id'][:12]}")
    console.print(f"  resume:  {result['resume_command']}")


@app.command("topics")
def topics_cmd(
    session_id: str = typer.Argument(..., help="Session ID or prefix"),
    force: bool = typer.Option(False, "--force", "-f", help="Regenerate even if topics exist"),
):
    """Generate or show topics for a session."""
    from calmlib.utils.patchbay import generate_topics, get_session

    session = get_session(session_id)
    if not session:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    if session.topics_short and not force:
        console.print(f"Topics: {session.topics_short}")
        return

    topics = generate_topics(session.session_id, force=force)
    if topics:
        console.print(f"Topics: {topics}")
    else:
        console.print("[dim]Could not generate topics (no messages?).[/dim]")


@app.command("resume")
def resume_cmd(
    session_id: str = typer.Argument(..., help="Session ID or prefix"),
):
    """Print the resume command for a session. Copies to clipboard."""
    from calmlib.utils.patchbay import get_session

    session = get_session(session_id)
    if not session:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    cwd = session.cwd or "."
    client = session.client or "claude"
    if client == "codex":
        cmd = f"cd {cwd} && codex resume {session.session_id}"
    elif client == "gemini":
        cmd = f"cd {cwd} && gemini --resume {session.session_id}"
    else:
        cmd = f"cd {cwd} && claude --resume {session.session_id}"

    console.print(cmd)
    try:
        import subprocess
        subprocess.run(["pbcopy"], input=cmd.encode(), check=True)
        console.print("  [dim](copied to clipboard)[/dim]")
    except Exception:
        pass


@app.command("status")
def status_cmd(
    session_id: str = typer.Argument(..., help="Session ID or prefix"),
):
    """Show detailed session status."""
    from calmlib.utils.patchbay import get_session

    session = get_session(session_id, refresh_metadata=True)
    if not session:
        console.print(f"[red]Session not found: {session_id}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]{session.title or '(no title)'}[/bold]")
    console.print(f"  ID:      {session.session_id}")
    console.print(f"  Status:  {session.status or 'new'}")
    console.print(f"  Client:  {session.client or 'unknown'}")
    console.print(f"  Source:  {session.source or 'unknown'}")
    if session.cwd:
        console.print(f"  CWD:     {session.cwd}")
    if session.project:
        console.print(f"  Project: [cyan]{session.project}[/cyan]")
    if session.task:
        console.print(f"  Task:    {session.task}")
    if session.task_id:
        console.print(f"  Task ID: {session.task_id}")
    if session.message_count:
        console.print(f"  Messages: {session.message_count}")
    if session.turn_count:
        console.print(f"  Turns:   {session.turn_count}")
    if session.total_cost_usd:
        console.print(f"  Cost:    ${session.total_cost_usd:.2f}")
    if session.wrapup_doc:
        console.print(f"  Wrapup:  [cyan]{session.wrapup_doc}[/cyan]")
    if session.tags:
        console.print(f"  Tags:    {', '.join(session.tags)}")
    if session.timestamp:
        console.print(f"  Created: {session.timestamp.strftime('%Y-%m-%d %H:%M')}")


def _format_date_label(dt: datetime) -> str:
    """Format date as a group header label (no time). E.g. 'Today', 'Yesterday', '6 Apr, Monday'."""
    now = datetime.now()
    today = now.date()
    d = dt.date() if isinstance(dt, datetime) else dt

    if d == today:
        return "Today"
    if d == today - timedelta(days=1):
        return "Yesterday"

    day_str = f"{d.day} {d.strftime('%b')}, {d.strftime('%A')}"
    if d.year != today.year:
        day_str = f"{d.day} {d.strftime('%b')} {d.year}, {d.strftime('%A')}"
    return day_str


def _format_week_label(d) -> str:
    """Format a week label like 'Week of 24 Mar'."""
    if isinstance(d, datetime):
        d = d.date()
    # Monday of that week
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    now = datetime.now().date()
    if monday.year != now.year:
        return f"Week of {monday.day} {monday.strftime('%b')} {monday.year}"
    return f"Week of {monday.day} {monday.strftime('%b')} – {sunday.day} {sunday.strftime('%b')}"


def _format_time(dt: datetime) -> str:
    """Format just the time portion for display within a date group."""
    return dt.strftime("%H:%M")


def _group_sessions_by_date(sessions: list) -> OrderedDict:
    """Group sessions by date with smart batching.

    Recent dates (Today, Yesterday, specific dates) get their own groups.
    Older dates beyond ~7 days are grouped by week to avoid a giant 'Older' blob.
    Groups are ordered newest-first; sessions within each group will be sorted later.
    """
    now = datetime.now()
    today = now.date()

    # Partition into per-date buckets first
    date_buckets: OrderedDict[str, list] = OrderedDict()
    # Track which actual date each label maps to, for sorting
    date_keys: dict[str, object] = {}

    for s in sessions:
        if not s.timestamp:
            label = "Unknown"
            date_keys.setdefault(label, datetime.min.date())
        else:
            d = s.timestamp.date()
            days_ago = (today - d).days
            if days_ago <= 6:
                # Recent: individual date groups
                label = _format_date_label(s.timestamp)
                date_keys.setdefault(label, d)
            else:
                # Older: group by week
                label = _format_week_label(d)
                date_keys.setdefault(label, d)

        date_buckets.setdefault(label, [])
        date_buckets[label].append(s)

    # Sort groups: newest date first (descending by representative date)
    sorted_labels = sorted(
        date_buckets.keys(),
        key=lambda lbl: date_keys.get(lbl, datetime.min.date()),
        reverse=True,
    )

    result: OrderedDict[str, list] = OrderedDict()
    for label in sorted_labels:
        result[label] = date_buckets[label]
    return result


def _format_date(dt: datetime) -> str:
    """Format date as '7 Apr, Monday' / 'Today' / 'Yesterday'. Year only if not current."""
    now = datetime.now()
    today = now.date()
    d = dt.date() if isinstance(dt, datetime) else dt

    if d == today:
        return f"Today, {dt.strftime('%H:%M')}"
    if d == today - timedelta(days=1):
        return f"Yesterday, {dt.strftime('%H:%M')}"

    day_str = f"{d.day} {d.strftime('%b')}, {d.strftime('%A')}"
    if d.year != today.year:
        day_str = f"{d.day} {d.strftime('%b')} {d.year}, {d.strftime('%A')}"
    return day_str


def _parse_since(since: str) -> datetime:
    """Parse '3d', '12h', '1w' into a datetime."""
    unit = since[-1]
    value = int(since[:-1])
    if unit == "d":
        return datetime.now() - timedelta(days=value)
    elif unit == "h":
        return datetime.now() - timedelta(hours=value)
    elif unit == "w":
        return datetime.now() - timedelta(weeks=value)
    raise typer.BadParameter(f"Unknown time unit: {unit}. Use d/h/w.")


@app.command("tui")
def tui_cmd(
    all_sources: bool = typer.Option(False, "--all", help="Show all sources"),
    ai: bool = typer.Option(False, "--ai", help="Show AI sessions only"),
    client: str = typer.Option(None, "-c", "--client", help="Filter: claude | codex | gemini"),
):
    """Interactive session browser (full-screen TUI)."""
    from calmlib.utils.patchbay.tui import run_tui

    source_filter = "human"
    if all_sources:
        source_filter = None
    elif ai:
        source_filter = "ai"
    run_tui(source_filter=source_filter, client=client)


if __name__ == "__main__":
    app()
