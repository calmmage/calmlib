"""Patchbay data models."""

from datetime import datetime

from pydantic import BaseModel, Field


class Topics(BaseModel):
    """Extracted keyword topics for a session."""

    keywords: list[str] = Field(description="2-4 short keyword topics describing what the session is about")


class SessionInfo(BaseModel):
    """Session metadata from MongoDB."""

    session_id: str
    client: str = "claude"
    source: str = "ai"
    status: str | None = None
    title: str | None = None
    title_source: str | None = None
    claude_custom_title: str | None = None
    claude_agent_name: str | None = None
    topics_short: str | None = None
    topic_keywords: list[str] | None = None
    timestamp: datetime | None = None
    last_activity_at: datetime | None = None
    cwd: str | None = None
    message_count: int | None = None
    first_message: str | None = None
    last_message: str | None = None
    project: str | None = None
    task: str | None = None
    task_id: str | None = None
    tags: list[str] | None = None
    turn_count: int | None = None
    total_cost_usd: float | None = None
    model: str | None = None
    wrapup_doc: str | None = None
    wrapup_invoked: bool | None = None

    def summary(self) -> str:
        parts = []
        parts.append(f"[{self.session_id[:12]}] {self.title or '(no title)'}")
        if self.topics_short:
            parts.append(f"  topics: {self.topics_short}")
        parts.append(f"  status: {self.status or 'new'}  source: {self.source}")
        if self.first_message:
            parts.append(f"  first: {self.first_message[:120]}")
        if self.timestamp:
            parts.append(f"  time: {self.timestamp.strftime('%Y-%m-%d %H:%M')}")
        return "\n".join(parts)
