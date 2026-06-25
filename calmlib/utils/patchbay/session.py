"""PatchbaySession — multi-turn SDK wrapper with MongoDB tracking."""

import os
from datetime import datetime

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
)
from loguru import logger

from calmlib.utils.claude_code.sdk import resolve_claude_code_model
from calmlib.utils.patchbay.query import get_collection, refresh_session_metadata, set_session_title

MAX_AI_SESSIONS_PER_HOUR = 20


def _check_runaway_protection():
    """Refuse to spawn if too many AI sessions created in the last hour."""
    from datetime import timedelta

    col = get_collection()
    cutoff = datetime.now() - timedelta(hours=1)
    recent_count = col.count_documents({
        "source": "ai",
        "timestamp": {"$gte": cutoff},
    })
    if recent_count >= MAX_AI_SESSIONS_PER_HOUR:
        raise RuntimeError(
            f"Runaway protection: {recent_count} AI sessions in the last hour "
            f"(limit: {MAX_AI_SESSIONS_PER_HOUR}). Refusing to spawn."
        )
    logger.debug(f"Runaway check: {recent_count}/{MAX_AI_SESSIONS_PER_HOUR} AI sessions in last hour")


class PatchbaySession:
    """Async context manager for multi-turn Claude sessions with MongoDB tracking.

    Usage:
        async with PatchbaySession(cwd="~/calmmage") as session:
            r1 = await session.send("What files are in this directory?")
            print(r1)
            r2 = await session.send("Now read the README")
            print(r2)
    """

    def __init__(
        self,
        cwd: str | None = None,
        system_prompt: str | None = None,
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        task_description: str | None = None,
        session_title: str | None = None,
        parent_session_id: str | None = None,
    ):
        self.cwd = cwd or os.getcwd()
        self.system_prompt = system_prompt
        self.model = model
        self.allowed_tools = allowed_tools or [
            "Read", "Glob", "Grep", "Bash", "Edit", "Write", "Task",
        ]
        self.task_description = task_description
        self.session_title = session_title
        self.parent_session_id = parent_session_id

        self._client: ClaudeSDKClient | None = None
        self._session_id: str | None = None
        self._total_cost: float = 0.0
        self._turn_count: int = 0

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def total_cost(self) -> float:
        return self._total_cost

    async def __aenter__(self) -> "PatchbaySession":
        _check_runaway_protection()

        resolved_model = resolve_claude_code_model(self.model)
        options = ClaudeAgentOptions(
            cwd=self.cwd,
            allowed_tools=self.allowed_tools,
            model=resolved_model,
        )
        if self.system_prompt:
            options.append_system_prompt = self.system_prompt

        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()
        logger.info(f"PatchbaySession connected (cwd={self.cwd})")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.disconnect()

        # Update MongoDB with final status
        if self._session_id:
            col = get_collection()
            status = "completed" if not exc_type else "failed"
            col.update_one(
                {"session_id": self._session_id},
                {"$set": {
                    "status": status,
                    "total_cost_usd": self._total_cost,
                    "turn_count": self._turn_count,
                }},
            )
            logger.info(
                f"PatchbaySession {self._session_id[:12]} {status} "
                f"({self._turn_count} turns, ${self._total_cost:.4f})"
            )

            # Sync Claude's custom title from JSONL into MongoDB
            try:
                refresh_session_metadata(self._session_id)
            except Exception as exc:
                logger.warning(f"Failed to refresh metadata on exit: {exc}")

        return False

    async def send(self, message: str) -> str:
        """Send a message and return the assistant's response text."""
        if not self._client:
            raise RuntimeError("Session not connected. Use 'async with PatchbaySession() as s:'")

        self._turn_count += 1
        logger.debug(f"Turn {self._turn_count}: sending {len(message)} chars")

        await self._client.query(message)

        response_parts: list[str] = []

        async for msg in self._client.receive_response():
            # Extract session_id from SystemMessage
            if isinstance(msg, SystemMessage):
                sid = msg.data.get("session_id")
                if sid and not self._session_id:
                    self._session_id = sid
                    logger.info(f"Session ID: {sid[:12]}")
                    self._register_in_mongo()
                    if self.session_title:
                        set_session_title(self._session_id, self.session_title, cwd=self.cwd)

            # Collect assistant text
            elif isinstance(msg, AssistantMessage):
                if hasattr(msg, "content"):
                    for block in msg.content:
                        if hasattr(block, "text"):
                            response_parts.append(block.text)

            # Track costs from ResultMessage
            elif isinstance(msg, ResultMessage):
                if hasattr(msg, "total_cost_usd") and msg.total_cost_usd:
                    self._total_cost += msg.total_cost_usd
                # Also check for session_id here
                if hasattr(msg, "session_id") and msg.session_id and not self._session_id:
                    self._session_id = msg.session_id
                    self._register_in_mongo()

        response = "\n".join(response_parts)
        logger.debug(f"Turn {self._turn_count}: got {len(response)} chars back")
        return response

    def _register_in_mongo(self):
        """Register this session in MongoDB with source='ai'."""
        col = get_collection()
        record = {
            "session_id": self._session_id,
            "client": "claude",
            "source": "ai",
            "cwd": self.cwd,
            "timestamp": datetime.now(),
        }
        if self.task_description:
            record["task_description"] = self.task_description
        if self.parent_session_id:
            record["parent_session_id"] = self.parent_session_id
        col.update_one(
            {"session_id": self._session_id},
            {"$set": record},
            upsert=True,
        )
        logger.info(f"Registered in MongoDB: {self._session_id[:12]} (source=ai)")
