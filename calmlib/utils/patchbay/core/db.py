"""Patchbay database layer — connection, collections, low-level helpers."""

import json
from pathlib import Path

from pymongo.collection import Collection

from calmlib.utils.patchbay.core.models import SessionInfo

DB_NAME = "coding_tasks"
COLLECTION_NAME = "agent_sessions"
EMPTY_COLLECTION_NAME = "empty_sessions"
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def _get_client():
    from pymongo import MongoClient
    from calmlib.utils import find_env_key

    uri = find_env_key("MONGODB_URI", default="mongodb://localhost:27017")
    return MongoClient(uri)


def get_collection() -> Collection:
    """Get the agent_sessions MongoDB collection."""
    return _get_client()[DB_NAME][COLLECTION_NAME]


def get_empty_collection() -> Collection:
    """Get the empty_sessions MongoDB collection (parking lot for 0-msg sessions)."""
    return _get_client()[DB_NAME][EMPTY_COLLECTION_NAME]


def _find_session_doc(col: Collection, session_id: str) -> dict | None:
    """Find a session document by exact ID or prefix."""
    doc = col.find_one({"session_id": session_id})
    if doc:
        return doc
    return col.find_one({"session_id": {"$regex": f"^{session_id}"}})


def _doc_to_session(doc: dict) -> SessionInfo:
    doc.pop("_id", None)
    known = SessionInfo.model_fields.keys()
    filtered = {k: v for k, v in doc.items() if k in known}
    return SessionInfo(**filtered)


def _find_claude_conversation_jsonl(session_id: str) -> Path | None:
    """Find the Claude per-project JSONL file for a session."""
    if not CLAUDE_PROJECTS_DIR.exists():
        return None

    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate
    return None
