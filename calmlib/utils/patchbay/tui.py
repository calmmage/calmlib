"""Patchbay TUI — browse and resume AI sessions."""

import os
from datetime import datetime, timedelta, timezone

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from calmlib.utils.patchbay.core.db import _find_claude_conversation_jsonl
from calmlib.utils.patchbay.core.models import SessionInfo
from calmlib.utils.patchbay.core.refresh import (
    bulk_refresh_metadata,
    refresh_session_metadata,
    sweep_empty_sessions,
)
from calmlib.utils.patchbay.core.search import (
    list_sessions,
    update_session_status,
)


def _age_str(ts) -> str:
    if not isinstance(ts, datetime):
        return "?"
    now = datetime.now(timezone.utc)
    age = now - ts.replace(tzinfo=timezone.utc)
    if age.days > 0:
        return f"{age.days}d"
    if age.seconds > 3600:
        return f"{age.seconds // 3600}h"
    return f"{age.seconds // 60}m"


def _abs_date_str(ts) -> str:
    """Human-friendly absolute date: 'today 14:32', 'yesterday 09:10', '19 Apr 12:33'."""
    if not isinstance(ts, datetime):
        return "?"
    local = ts.replace(tzinfo=timezone.utc).astimezone() if ts.tzinfo else ts
    today = datetime.now().date()
    d = local.date()
    if d == today:
        return f"today {local.strftime('%H:%M')}"
    if (today - d).days == 1:
        return f"yesterday {local.strftime('%H:%M')}"
    if d.year == today.year:
        return local.strftime("%-d %b %H:%M")
    return local.strftime("%-d %b %Y %H:%M")


def _full_date_pair(ts) -> str:
    """Both relative and absolute, e.g. '2h ago  ·  yesterday 14:32'."""
    if not isinstance(ts, datetime):
        return "?"
    return f"{_age_str(ts)}  [dim]·[/]  {_abs_date_str(ts)}"


def _short_path(p: str | None) -> str:
    if not p:
        return "?"
    home = str(os.path.expanduser("~"))
    if p.startswith(home):
        return "~" + p[len(home):]
    return p


CLIENT_COLORS = {
    "claude": "orange1",
    "codex": "green",
    "chatgpt": "green",
    "gemini": "deep_sky_blue1",
}


def _client_markup(client: str | None) -> str:
    name = client or "?"
    color = CLIENT_COLORS.get(name, "white")
    return f"[bold {color}]{name}[/]"


STATUS_COLORS = {
    "new": "cyan",
    "summarized": "white",
    "completed": "green",
    "done": "green",
    "archived": "grey50",
    "empty": "grey50",
    "dismissed": "grey50",
    "failed": "red",
}


def _status_markup(status: str | None) -> str:
    name = status or "new"
    color = STATUS_COLORS.get(name, "white")
    return f"[{color}]{name}[/]"


def _topic_list(session: SessionInfo) -> list[str]:
    if session.topic_keywords:
        return [k for k in session.topic_keywords if k]
    if session.topics_short:
        return [k.strip() for k in session.topics_short.split(",") if k.strip()]
    return []


def _row_title(session: SessionInfo) -> str:
    """Pick the best label for the row title — prefer Claude's own title."""
    return (
        session.claude_custom_title
        or session.claude_agent_name
        or session.title
        or session.session_id[:16] + "…"
    )


def _trim(text: str, n: int) -> str:
    text = " ".join((text or "").split())  # collapse whitespace
    if len(text) > n:
        return text[: n - 1] + "…"
    return text


PROJECT_ICONS = {
    "plaintask": "📋",
    "patchbay": "🔌",
    "calmlib": "📚",
    "calmmage": "🏰",
    "obsidian": "🔮",
    "telegram": "💬",
    "botspot": "🤖",
    "textvault": "🗃️",
    "nas": "💾",
    "automations": "⏱️",
}

TYPE_KEYWORDS = [
    ("🐛", ("fix", "bug", "issue", "error", "debug", "broken", "crash")),
    ("⚙️", ("setup", "config", "deploy", "install", "infrastructure", "launchd", "cron")),
    ("🧪", ("experiment", "prototype", "explore", "try", "test")),
    ("🛠️", ("build", "create", "implement", "add", "new", "scaffold")),
    ("♻️", ("refactor", "cleanup", "reorganize", "migrate", "rewrite")),
    ("🔍", ("review", "audit", "analyze", "inspect")),
    ("📝", ("doc", "documentation", "writeup", "note")),
    ("🔎", ("research", "investigate")),
]


def _row_icon(s: SessionInfo) -> str:
    """Single semantic icon. Priority: tags → wrapup → topic-type → project → fallback."""
    tags = set(s.tags or [])
    if tags & {"fav", "⭐"}:
        return "⭐"
    if tags & {"hot", "🔥"}:
        return "🔥"
    if tags & {"cool", "❄️"}:
        return "❄️"

    if s.wrapup_invoked:
        return "🏁"

    topics_blob = " ".join(_topic_list(s)).lower()
    title_blob = (s.title or "").lower()
    blob = f"{topics_blob} {title_blob}"
    for icon, words in TYPE_KEYWORDS:
        if any(w in blob for w in words):
            return icon

    project = (s.project or "").lower()
    if project:
        for key, ic in PROJECT_ICONS.items():
            if key in project:
                return ic

    cwd = (s.cwd or "").lower()
    for key, ic in PROJECT_ICONS.items():
        if f"/{key}" in cwd:
            return ic

    return "·"


def _msg_count_markup(c: int | None) -> str:
    """Color-code message count by bucket: -/small/med/large."""
    if c is None or c <= 0:
        return "[dim]  -[/]"
    txt = f"{c:>3}"
    if c < 5:
        return f"[green]{txt}[/]"
    if c < 20:
        return f"[yellow]{txt}[/]"
    return f"[bold magenta]{txt}[/]"


def _format_row(session: SessionInfo) -> str:
    """Single-line row with markup: icon · age · msgs · title · topics."""
    icon = _row_icon(session)
    age = _age_str(session.last_activity_at or session.timestamp)
    msgs = _msg_count_markup(session.message_count)
    title = _trim(_row_title(session), 60)
    status = session.status or ""
    status_tag = f" \\[{status}]" if status in ("empty", "archived", "done") else ""
    project = f" [dim]· {session.project}[/]" if session.project else ""
    topics = _topic_list(session)
    topic_str = f"  [dim]⟨{', '.join(topics)}⟩[/]" if topics else ""

    return f"{icon} [dim]{age:>5}[/] │ {msgs} │ {title}{status_tag}{project}{topic_str}"


def _header_row() -> str:
    return f"   {'age':>5} │ {'msg':>3} │ title"


def _format_preview(session: SessionInfo, *, full: bool = False) -> str:
    """Rich-markup preview for the side pane / modal. `full=True` un-caps message text."""
    cap = 2000 if full else 500
    width = 72 if full else 50
    bar = "─" * width

    lines: list[str] = []

    # Title block
    icon = _row_icon(session)
    title = _row_title(session)
    lines.append(f"[bold]{icon}  {title}[/]")
    own = session.claude_custom_title or session.claude_agent_name
    if own and session.title and session.title != own:
        lines.append(f"   [dim]styled:[/] {session.title}")
    lines.append("")

    # Identity line
    lines.append(
        f"{_client_markup(session.client)}  [dim]·[/]  "
        f"[cyan]{session.source}[/]  [dim]·[/]  {_status_markup(session.status)}"
    )

    # When
    when_ts = session.last_activity_at or session.timestamp
    if session.last_activity_at and session.last_activity_at != session.timestamp:
        lines.append(
            f"[dim]last activity:[/]  {_full_date_pair(session.last_activity_at)}"
        )
        if session.timestamp:
            lines.append(f"[dim]created:     [/]  {_abs_date_str(session.timestamp)}")
    elif when_ts:
        lines.append(f"[dim]created:[/]  {_full_date_pair(when_ts)}")

    # Stats
    stats = []
    if session.message_count:
        c = session.message_count
        if c < 5:
            stats.append(f"[green]{c}[/] msgs")
        elif c < 20:
            stats.append(f"[yellow]{c}[/] msgs")
        else:
            stats.append(f"[bold magenta]{c}[/] msgs")
    if session.model:
        stats.append(f"[dim]{session.model}[/]")
    if session.total_cost_usd:
        stats.append(f"[bold]${session.total_cost_usd:.2f}[/]")
    if stats:
        lines.append("  ".join(stats))

    # Identity / location — full session id, no truncation
    lines.append(
        f"[dim]{session.session_id}  ·  {_short_path(session.cwd)}[/]"
    )

    # Topics / project / tags
    info_lines: list[str] = []
    topics = _topic_list(session)
    if topics:
        info_lines.append(
            "[dim]topics:[/]  " + "  ".join(f"[cyan]⟨{t}⟩[/]" for t in topics)
        )
    if session.project:
        info_lines.append(f"[dim]project:[/] [magenta]{session.project}[/]")
    if session.task and session.task != session.project:
        info_lines.append(f"[dim]task:[/]    [magenta]{session.task}[/]")
    if session.tags:
        info_lines.append(
            "[dim]tags:[/]    " + "  ".join(f"[yellow]{t}[/]" for t in session.tags)
        )
    if session.wrapup_invoked:
        info_lines.append("[bold yellow]🏁 /session-wrapup invoked[/] [dim](may be incomplete)[/]")
    if info_lines:
        lines.append("")
        lines.extend(info_lines)

    # Messages
    lines.append("")
    lines.append(f"[bold magenta]{bar}[/]")
    lines.append("[bold magenta]  First message[/]")
    lines.append(f"[bold magenta]{bar}[/]")
    if session.first_message:
        lines.append(session.first_message[:cap])
    else:
        lines.append("[dim](none yet — press R to refresh)[/]")

    if session.last_message and session.last_message != session.first_message:
        lines.append("")
        lines.append(f"[bold cyan]{bar}[/]")
        lines.append("[bold cyan]  Last message[/]")
        lines.append(f"[bold cyan]{bar}[/]")
        lines.append(session.last_message[:cap])

    return "\n".join(lines)


class JumpListView(ListView):
    """ListView that doesn't wrap on cursor_up/down and supports jump-to-top/bottom."""

    BINDINGS = [
        Binding("home", "jump_top", "Top", show=False),
        Binding("end", "jump_bottom", "Bottom", show=False),
        Binding("ctrl+home", "jump_top", "Top", show=False),
        Binding("ctrl+end", "jump_bottom", "Bottom", show=False),
        Binding("g", "jump_top", "Top", show=False),
        Binding("G", "jump_bottom", "Bottom", show=False),
        Binding("super+up", "jump_top", "Top", show=False),
        Binding("super+down", "jump_bottom", "Bottom", show=False),
    ]

    def action_cursor_up(self) -> None:
        if not len(self):
            return
        if self.index is None or self.index <= 0:
            self.index = 0
            return
        self.index -= 1

    def action_cursor_down(self) -> None:
        if not len(self):
            return
        if self.index is None:
            self.index = 0
            return
        if self.index >= len(self) - 1:
            return
        self.index += 1

    def action_jump_top(self) -> None:
        if len(self):
            self.index = 0

    def action_jump_bottom(self) -> None:
        if len(self):
            self.index = len(self) - 1


HELP_TEXT = """\
[bold cyan]── Navigation ──[/]
  [yellow]↑ ↓[/]            move selection
  [yellow]home[/] / [yellow]g[/]      jump to top
  [yellow]end[/] / [yellow]G[/]       jump to bottom
  [yellow]enter[/] / click   open preview → enter resumes

[bold cyan]── View filters ──[/]
  [yellow]o[/]              show / hide old (>7d)
  [yellow]s[/]              cycle source: human → AI → all
  [yellow]t[/]              show / hide archived

[bold cyan]── Preview pane ──[/]
  [yellow]pgup[/] / [yellow]pgdn[/]   scroll preview by page
  [yellow][[/] / [yellow]][/]        scroll preview by line
  mouse wheel    scroll preview

[bold cyan]── Actions ──[/]
  [yellow]a[/]              archive selected
  [yellow]d[/]              dismiss selected
  [yellow]r[/]              regenerate title for selected
  [yellow]R[/]              refresh all metadata (backfill new fields)
  [yellow]w[/]              sweep empty sessions (>1h, no real msgs)

[bold cyan]── Misc ──[/]
  [yellow]?[/]              this help
  [yellow]q[/] / [yellow]esc[/]        quit

[bold magenta]── Row icon legend ──[/]
  [bold]Tags[/]      ⭐ favorite   🔥 hot      ❄️ cool
  [bold]State[/]     🏁 /session-wrapup invoked (may be unfinished)
  [bold]Type[/]      🐛 bugfix     ⚙️ setup    🧪 experiment
              🛠️ build       ♻️ refactor  🔍 review
              📝 docs       🔎 research
  [bold]Project[/]  🔌 patchbay    📋 plaintask  📚 calmlib
              🏰 calmmage    🔮 obsidian   💬 telegram
              🤖 botspot     🗃️ textvault  💾 nas
              ⏱️ automations
  [bold]Default[/]  ·  uncategorized

[bold magenta]── Message-count colors ──[/]
  [green]small[/] (<5)    [yellow]medium[/] (5-19)    [bold magenta]large[/] (20+)

[bold magenta]── Client colors ──[/]
  [bold orange1]claude[/]    [bold green]codex[/] / [bold green]chatgpt[/]    [bold deep_sky_blue1]gemini[/]

[dim]Press any key to close.[/]
"""


class HelpScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-box {
        width: 80%;
        height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #help-body {
        height: 1fr;
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
        Binding("q", "close", "Close", show=False),
        Binding("?", "close", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(HELP_TEXT, id="help-body")

    def action_close(self) -> None:
        self.dismiss(None)


class PreviewScreen(ModalScreen[str]):
    """Detailed preview of a session before resuming.

    Returns: "resume" to launch, anything else (or None) to back out.
    """

    DEFAULT_CSS = """
    PreviewScreen {
        align: center middle;
    }
    #preview-box {
        width: 90%;
        height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    #preview-title {
        height: auto;
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }
    #preview-body {
        height: 1fr;
        overflow-y: auto;
    }
    #preview-actions {
        height: 1;
        color: $text-muted;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("enter", "resume", "Resume", show=True),
        Binding("escape", "cancel", "Back", show=True),
        Binding("q", "cancel", "Back", show=False),
    ]

    def __init__(self, session: SessionInfo) -> None:
        super().__init__()
        self.session = session

    def compose(self) -> ComposeResult:
        with Vertical(id="preview-box"):
            yield Static(_row_title(self.session), id="preview-title")
            yield Static(_format_preview(self.session, full=True), id="preview-body")
            yield Static(
                "[ Enter ] resume    [ Esc ] back",
                id="preview-actions",
            )

    def action_resume(self) -> None:
        self.dismiss("resume")

    def action_cancel(self) -> None:
        self.dismiss("cancel")


class SessionListApp(App):
    """Browse and resume AI coding sessions."""

    TITLE = "Patchbay Sessions"
    CSS = """
    #main-h {
        layout: horizontal;
        height: 1fr;
    }
    #main-h #list-pane { width: 3fr; }
    #main-h #preview-scroll {
        width: 2fr;
        border-left: solid $accent;
    }
    #main-v {
        layout: vertical;
        height: 1fr;
    }
    #main-v #list-pane { height: 2fr; }
    #main-v #preview-scroll {
        height: 1fr;
        border-top: solid $accent;
    }
    #col-header {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }
    #sessions {
        height: 1fr;
    }
    #preview-scroll {
        padding: 1 2;
    }
    #preview-scroll:focus {
        border: tall $warning;
    }
    #preview-pane {
        height: auto;
    }
    .archived-item { color: $text-muted; }
    .empty-item { color: $text-disabled; }
    .stale-item { color: $text-muted; }
    .separator-item {
        color: $accent;
        text-style: italic;
    }
    """
    BINDINGS = [
        # Visible — most-used
        Binding("enter", "open_preview", "Open"),
        Binding("space", "toggle_select", "Select"),
        Binding("b", "bundle", "Bundle"),
        Binding("B", "quick_batch", "Quick-batch"),
        Binding("?", "show_help", "Help"),
        Binding("R", "refresh_all", "Refresh"),
        Binding("o", "toggle_old", "Old"),
        Binding("s", "toggle_source", "Source"),
        Binding("q", "quit", "Quit"),
        # Hidden — discoverable via ?
        Binding("escape", "quit", "Quit", show=False),
        Binding("a", "archive", "Archive", show=False),
        Binding("d", "dismiss_session", "Dismiss", show=False),
        Binding("t", "toggle_archived", "Toggle archived", show=False),
        Binding("w", "sweep", "Sweep empty", show=False),
        Binding("r", "regen_title", "Regen title", show=False),
        Binding("X", "clear_selection", "Clear selection", show=False),
        # Preview-pane scroll (mouse wheel works too)
        Binding("pageup", "preview_pgup", "Preview ↑", show=False),
        Binding("pagedown", "preview_pgdn", "Preview ↓", show=False),
        Binding("[", "preview_up", "Preview line ↑", show=False),
        Binding("]", "preview_down", "Preview line ↓", show=False),
    ]

    WIDE_THRESHOLD = 160
    STALE_DAYS = 7

    def __init__(self, source_filter: str | None = "human", client: str | None = None):
        super().__init__()
        self.source_filter = source_filter
        self.client_filter = client
        self.show_archived = False
        self.show_old = False
        self.sessions: list[SessionInfo] = []
        self.row_sessions: list[SessionInfo | None] = []
        # multi-select state for bundle-into-worksession
        self.selected_ids: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        wide = self.size.width >= self.WIDE_THRESHOLD if self.size.width else False
        container_cls = Horizontal if wide else Vertical
        container_id = "main-h" if wide else "main-v"
        with container_cls(id=container_id):
            with Vertical(id="list-pane"):
                yield Static(_header_row(), id="col-header")
                yield JumpListView(id="sessions")
            with VerticalScroll(id="preview-scroll"):
                yield Static("Select a session to preview", id="preview-pane")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        human_only = self.source_filter == "human"
        status = "archived" if self.show_archived else None
        self.sessions = list_sessions(
            human_only=human_only if self.source_filter != "ai" else False,
            limit=200,
            status=status,
            client=self.client_filter,
        )
        if self.source_filter == "ai":
            self.sessions = [s for s in self.sessions if s.source == "ai"]

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.STALE_DAYS)
        recent: list[SessionInfo] = []
        stale: list[SessionInfo] = []
        for s in self.sessions:
            t = s.last_activity_at or s.timestamp
            if t and t.replace(tzinfo=timezone.utc) >= cutoff:
                recent.append(s)
            else:
                stale.append(s)

        lv = self.query_one("#sessions", JumpListView)
        prev_index = lv.index
        prev_session = self._session_at(prev_index)
        prev_session_id = prev_session.session_id if prev_session else None
        lv.clear()
        self.row_sessions = []

        if self.selected_ids:
            n = len(self.selected_ids)
            hint = (
                f"── {n} selected — press 'b' to bundle into a worksession "
                f"· X to clear ──"
            )
            lv.append(ListItem(Label(hint, classes="separator-item")))
            self.row_sessions.append(None)

        for s in recent:
            classes = self._row_classes(s)
            lv.append(ListItem(Label(self._format_row_sel(s), classes=classes)))
            self.row_sessions.append(s)

        if stale:
            verb = "hide" if self.show_old else "show"
            sep_label = (
                f"── {len(stale)} older session{'s' if len(stale) != 1 else ''} "
                f"(>{self.STALE_DAYS}d) — press 'o' to {verb} ──"
            )
            lv.append(ListItem(Label(sep_label, classes="separator-item")))
            self.row_sessions.append(None)

            if self.show_old:
                for s in stale:
                    classes = self._row_classes(s, stale=True)
                    lv.append(ListItem(Label(self._format_row_sel(s), classes=classes)))
                    self.row_sessions.append(s)

        if self.row_sessions:
            new_index = None
            if prev_session_id is not None:
                for i, rs in enumerate(self.row_sessions):
                    if rs is not None and rs.session_id == prev_session_id:
                        new_index = i
                        break
            if new_index is None:
                new_index = 0 if prev_index is None else min(prev_index, len(self.row_sessions) - 1)
            lv.index = new_index
        self._update_preview()

    def _format_row_sel(self, s: SessionInfo) -> str:
        """_format_row with a leading selection marker (●/space) for alignment."""
        base = _format_row(s)
        mark = "[bold cyan]●[/]" if s.session_id in self.selected_ids else " "
        return f"{mark} {base}"

    def _row_classes(self, s: SessionInfo, stale: bool = False) -> str:
        if s.status == "archived":
            return "archived-item"
        if s.status == "empty":
            return "empty-item"
        if stale:
            return "stale-item"
        return ""

    def _update_preview(self) -> None:
        lv = self.query_one("#sessions", JumpListView)
        idx = lv.index
        preview = self.query_one("#preview-pane", Static)
        s = self._session_at(idx)
        if s is not None:
            preview.update(_format_preview(s))
        else:
            preview.update("Select a session to preview")

    def _session_at(self, idx: int | None) -> SessionInfo | None:
        if idx is None or idx < 0 or idx >= len(self.row_sessions):
            return None
        return self.row_sessions[idx]

    @on(ListView.Highlighted, "#sessions")
    def on_highlight(self, event: ListView.Highlighted) -> None:
        self._update_preview()

    @on(ListView.Selected, "#sessions")
    def on_select(self, event: ListView.Selected) -> None:
        # Click no longer auto-resumes — just opens preview.
        self.action_open_preview()

    def _selected(self) -> SessionInfo | None:
        lv = self.query_one("#sessions", JumpListView)
        return self._session_at(lv.index)

    def action_toggle_select(self) -> None:
        s = self._selected()
        if s is None:
            return
        if s.session_id in self.selected_ids:
            self.selected_ids.discard(s.session_id)
        else:
            self.selected_ids.add(s.session_id)
        self._refresh_list()

    def action_clear_selection(self) -> None:
        if not self.selected_ids:
            return
        self.selected_ids.clear()
        self._refresh_list()

    QUICK_BATCH_SIZE = 5

    def action_quick_batch(self) -> None:
        """Take the N most-recent unsorted sessions (skipping daily-assistant and
        anything already in a worksession) and bundle them into a fresh worksession
        for later triage. No selection required."""
        try:
            from tools.task_management.plaintask.core.worksession_ops import (
                add_session_to_worksession,
                create_standalone_worksession,
            )
            from tools.task_management.plaintask.db import list_worksessions
        except Exception as exc:
            self.notify(f"plaintask not importable: {exc}", severity="error", timeout=3)
            return

        claimed: set[str] = set()
        for w in list_worksessions():
            claimed.update(w.session_ids)

        candidates: list[SessionInfo] = []
        for s in self.sessions:
            if s.session_id in claimed:
                continue
            if s.status in ("archived", "dismissed", "done", "empty"):
                continue
            title = (s.title or "").lower()
            if title.startswith("daily assistant") or title.startswith("daily agent"):
                continue
            candidates.append(s)
            if len(candidates) >= self.QUICK_BATCH_SIZE:
                break

        if len(candidates) < 2:
            self.notify(
                f"Only {len(candidates)} unsorted sessions found — nothing to batch.",
                severity="warning",
                timeout=2.5,
            )
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        ws_title = f"Triage batch {ts}"
        try:
            ws = create_standalone_worksession(title=ws_title)
            for s in candidates:
                add_session_to_worksession(ws.slug, s.session_id)
        except Exception as exc:
            self.notify(f"Quick batch failed: {exc}", severity="error", timeout=3)
            return
        self.notify(
            f"Batched {len(candidates)} sessions → '{ws_title}' (open with `ws`)",
            timeout=3,
        )
        self._refresh_list()

    def action_bundle(self) -> None:
        n = len(self.selected_ids)
        if n < 2:
            self.notify(
                f"Select at least 2 sessions (press space). Currently selected: {n}.",
                severity="warning",
                timeout=2.5,
            )
            return
        try:
            from tools.task_management.plaintask.core.worksession_ops import (
                add_session_to_worksession,
                create_standalone_worksession,
            )
        except Exception as exc:
            self.notify(f"plaintask not importable: {exc}", severity="error", timeout=3)
            return
        title = f"Session batch {datetime.now().strftime('%Y-%m-%d')}"
        picked = list(self.selected_ids)
        try:
            ws = create_standalone_worksession(title=title)
            for sid in picked:
                add_session_to_worksession(ws.slug, sid)
        except Exception as exc:
            self.notify(f"Bundle failed: {exc}", severity="error", timeout=3)
            return
        self.selected_ids.clear()
        self.notify(f"Bundled {n} sessions → '{title}' (open with `ws`)", timeout=3)
        self._refresh_list()

    def action_archive(self) -> None:
        s = self._selected()
        if s is None:
            return
        new_status = "summarized" if s.status == "archived" else "archived"
        update_session_status(s.session_id, new_status)
        self.notify(f"{s.session_id[:12]} → {new_status}")
        self._refresh_list()

    def action_dismiss_session(self) -> None:
        s = self._selected()
        if s is None:
            return
        update_session_status(s.session_id, "dismissed")
        self.notify(f"{s.session_id[:12]} dismissed")
        self._refresh_list()

    def action_toggle_archived(self) -> None:
        self.show_archived = not self.show_archived
        self._update_title()
        self._refresh_list()

    def action_toggle_old(self) -> None:
        self.show_old = not self.show_old
        self._refresh_list()

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def _preview_scroll(self) -> VerticalScroll | None:
        try:
            return self.query_one("#preview-scroll", VerticalScroll)
        except Exception:
            return None

    def action_preview_pgup(self) -> None:
        sc = self._preview_scroll()
        if sc:
            sc.scroll_page_up()

    def action_preview_pgdn(self) -> None:
        sc = self._preview_scroll()
        if sc:
            sc.scroll_page_down()

    def action_preview_up(self) -> None:
        sc = self._preview_scroll()
        if sc:
            sc.scroll_up()

    def action_preview_down(self) -> None:
        sc = self._preview_scroll()
        if sc:
            sc.scroll_down()

    def action_toggle_source(self) -> None:
        if self.source_filter == "human":
            self.source_filter = "ai"
        elif self.source_filter == "ai":
            self.source_filter = None
        else:
            self.source_filter = "human"
        self._update_title()
        self._refresh_list()

    def action_sweep(self) -> None:
        count = sweep_empty_sessions(max_age_hours=1, dry_run=False)
        self.notify(f"Swept {count} empty sessions", severity="information")
        self._refresh_list()

    def action_regen_title(self) -> None:
        s = self._selected()
        if s is None:
            return
        self.notify(f"Regenerating title for {s.session_id[:12]}…")
        self._regen_title_worker(s.session_id)

    def action_refresh_all(self) -> None:
        self.notify("Refreshing recent sessions…")
        self._refresh_all_worker()

    def action_open_preview(self) -> None:
        s = self._selected()
        if s is None:
            return
        if s.client == "claude" and not _find_claude_conversation_jsonl(s.session_id):
            update_session_status(s.session_id, "archived")
            self.notify(f"{s.session_id[:12]}… not found — archived", severity="warning")
            self._refresh_list()
            return

        def _on_close(result: str | None) -> None:
            if result == "resume":
                self.exit(s)

        self.push_screen(PreviewScreen(s), _on_close)

    @work(thread=True, exclusive=True)
    def _refresh_all_worker(self) -> None:
        human_only = self.source_filter == "human"
        try:
            updated = bulk_refresh_metadata(human_only=human_only)
        except Exception as exc:
            self.call_from_thread(
                self.notify,
                f"Refresh failed: {exc}",
                severity="error",
            )
            return
        self.call_from_thread(
            self.notify,
            f"Refreshed {len(updated)} sessions",
            severity="information",
        )
        self.call_from_thread(self._refresh_list)

    @work(thread=True, exclusive=False)
    def _regen_title_worker(self, session_id: str) -> None:
        try:
            updated = refresh_session_metadata(session_id, force=True)
        except Exception as exc:
            self.call_from_thread(
                self.notify,
                f"Title regen failed: {exc}",
                severity="error",
            )
            return
        new_title = updated.title if updated else None
        msg = f"Title: {new_title}" if new_title else "Refresh done — no title"
        self.call_from_thread(self.notify, msg, severity="information")
        self.call_from_thread(self._refresh_list)

    def _update_title(self) -> None:
        parts = ["Patchbay Sessions"]
        if self.source_filter:
            parts.append(f"[{self.source_filter}]")
        if self.show_archived:
            parts.append("(+ archived)")
        self.title = " ".join(parts)


def _resume_session(session: SessionInfo) -> None:
    """Replace current process with the session's client."""
    cwd = session.cwd
    if cwd and os.path.isdir(cwd):
        os.chdir(cwd)
    client = session.client or "claude"
    if client == "codex":
        os.execlp("codex", "codex", "resume", session.session_id)
    elif client == "gemini":
        os.execlp("gemini", "gemini", "--resume", session.session_id)
    else:
        os.execlp(
            "claude",
            "claude",
            "--resume",
            session.session_id,
        )


def run_tui(source_filter: str | None = "human", client: str | None = None) -> None:
    """Launch the session list TUI. Resumes selected session on exit."""
    app = SessionListApp(source_filter=source_filter, client=client)
    result = app.run()
    if result and isinstance(result, SessionInfo):
        _resume_session(result)
