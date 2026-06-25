"""
Claude Code conversation history utilities - ClaudeCodeUI approach

Based on the claudecodeui implementation with improvements:
- Proper project directory extraction from JSONL cwd field
- Session grouping and pagination
- Better error handling
- Dismissed conversations tracking with MongoDB
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pymongo import MongoClient


class ConversationMetadata(BaseModel):
    """Conversation metadata stored in MongoDB - just tracks dismissed status."""

    conversation_id: str = Field(..., description="Claude Code conversation ID")
    dismissed: bool = Field(False, description="Whether conversation is dismissed")

    class Config:
        arbitrary_types_allowed = True


def get_mongo_connection(
    mongo_uri: str = "mongodb://localhost:27017",
) -> tuple[MongoClient, Any]:
    """Get MongoDB connection and collection for conversations."""
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        db = client["coding_tasks"]
        collection = db["conversations"]
        return client, collection
    except Exception as e:
        raise RuntimeError(
            f"MongoDB not available at {mongo_uri}. "
            "Please start MongoDB: docker start mongodb"
        ) from e


def get_claude_home() -> Path:
    """Get Claude home directory"""
    return Path.home() / ".claude"


def extract_project_directory(project_name: str) -> str:
    """Extract actual project directory from JSONL sessions

    Reads cwd field from sessions to determine the real project path,
    as the encoded directory name may not match the actual working directory.

    Args:
        project_name: Encoded project name

    Returns:
        Actual project path used in sessions
    """
    project_dir = get_claude_home() / "projects" / project_name
    cwd_counts = defaultdict(int)

    for jsonl_file in project_dir.glob("*.jsonl"):
        with open(jsonl_file) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("cwd"):
                        cwd_counts[entry["cwd"]] += 1
                except json.JSONDecodeError:
                    continue

    # Return most common cwd, or decoded name as fallback
    if cwd_counts:
        return max(cwd_counts.items(), key=lambda x: x[1])[0]

    return project_name.replace("-", "/")


def list_projects(include_stats: bool = True) -> list[dict[str, Any]]:
    """List all Claude Code projects with enhanced metadata

    Args:
        include_stats: Whether to include session statistics

    Returns:
        List of projects with name, path, display_name, sessions
    """
    import warnings

    warnings.warn(
        "list_projects() is deprecated, use calmlib.utils.patchbay for session queries",
        DeprecationWarning,
        stacklevel=2,
    )
    projects_dir = get_claude_home() / "projects"
    if not projects_dir.exists():
        return []

    projects = []
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # Extract actual project directory
        actual_path = extract_project_directory(project_dir.name)
        display_name = Path(actual_path).name

        project = {
            "name": project_dir.name,
            "path": actual_path,
            "display_name": display_name,
            "full_path": actual_path,
        }

        if include_stats:
            # Get sessions for stats
            sessions = list_conversations(project_dir.name, limit=5)
            jsonl_files = list(project_dir.glob("*.jsonl"))

            project["sessions"] = sessions
            project["total_sessions"] = len(jsonl_files)

            # Calculate total messages across all sessions
            total_messages = sum(s["message_count"] for s in sessions)
            project["total_messages_preview"] = total_messages

        projects.append(project)

    return projects


def get_project_stats() -> dict[str, Any]:
    """Get overall statistics about all projects

    Returns:
        Dictionary with counts and aggregated stats
    """
    projects = list_projects(include_stats=True)

    return {
        "total_projects": len(projects),
        "total_sessions": sum(p.get("total_sessions", 0) for p in projects),
        "projects_by_path": {p["full_path"]: p["name"] for p in projects},
    }


def build_project_tree() -> dict[str, Any]:
    """Build a tree structure of nested projects

    Returns:
        Nested dictionary representing project hierarchy
    """
    projects = list_projects(include_stats=False)

    # Build tree structure
    tree = {}

    for project in projects:
        path = Path(project["full_path"])
        parts = path.parts

        # Navigate/build tree
        current = tree
        for i, part in enumerate(parts):
            if part not in current:
                current[part] = {
                    "_children": {},
                    "_is_project": False,
                    "_project_data": None,
                }

            # Mark as project if this is the full path
            if i == len(parts) - 1:
                current[part]["_is_project"] = True
                current[part]["_project_data"] = project

            current = current[part]["_children"]

    return tree


def format_project_tree(tree: dict[str, Any] = None, indent: int = 0) -> str:
    """Format project tree as a string with indentation

    Args:
        tree: Tree structure from build_project_tree()
        indent: Current indentation level

    Returns:
        Formatted tree string
    """
    if tree is None:
        tree = build_project_tree()

    lines = []

    def _format_node(node_dict: dict[str, Any], prefix: str, is_last: bool = False):
        for i, (name, data) in enumerate(sorted(node_dict.items())):
            is_last_child = i == len(node_dict) - 1
            connector = "└── " if is_last_child else "├── "
            continuation = "    " if is_last_child else "│   "

            # Format this node
            marker = "📁" if data["_is_project"] else "📂"
            lines.append(f"{prefix}{connector}{marker} {name}")

            # Recurse into children
            if data["_children"]:
                new_prefix = prefix + continuation
                _format_node(data["_children"], new_prefix, is_last_child)

    _format_node(tree, "")
    return "\n".join(lines)


def _is_system_message(content: str) -> bool:
    """Check if a message looks like a system/caveat message."""
    if not isinstance(content, str):
        return False

    # Common patterns for system messages and command outputs
    system_patterns = [
        "caveat:",
        "<system",
        "<command",
        "<local-command",
        "the messages below were generated",
        "context for this conversation",
        "you are claude",
        "you are an ai assistant",
    ]

    content_lower = content.lower().strip()
    return any(pattern in content_lower for pattern in system_patterns)


def _is_meaningful_message(content: str) -> bool:
    """Check if a message is substantial enough to be a summary."""
    if not isinstance(content, str):
        return False

    content = content.strip()

    # Too short
    if len(content) < 10:
        return False

    # Common filler messages
    filler_messages = [
        "ok",
        "okay",
        "thanks",
        "thank you",
        "yes",
        "no",
        "sure",
        "great",
        "sounds good",
        "perfect",
        "got it",
        "understood",
    ]

    if content.lower() in filler_messages:
        return False

    return True


def list_conversations(
    project_name: str, limit: int | None = None, offset: int = 0
) -> list[dict[str, Any]]:
    """List conversations in a project with pagination

    Args:
        project_name: Encoded project name
        limit: Maximum number of conversations to return
        offset: Number of conversations to skip

    Returns:
        List of conversations sorted by last activity
    """
    import warnings

    warnings.warn(
        "list_conversations() is deprecated, use calmlib.utils.patchbay.list_sessions() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    project_dir = get_claude_home() / "projects" / project_name
    if not project_dir.exists():
        return []

    sessions = {}
    entries = []
    # Track user and assistant messages per session for better summary selection
    session_user_messages = defaultdict(list)
    session_assistant_messages = defaultdict(list)

    # Parse all JSONL files
    for jsonl_file in sorted(project_dir.glob("*.jsonl")):
        with open(jsonl_file) as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    entries.append(entry)

                    session_id = entry.get("sessionId")
                    if not session_id:
                        continue

                    if session_id not in sessions:
                        sessions[session_id] = {
                            "id": session_id,
                            "summary": "New Session",
                            "message_count": 0,
                            "last_activity": None,
                            "cwd": entry.get("cwd", ""),
                        }

                    session = sessions[session_id]
                    session["message_count"] += 1

                    # Collect user and assistant messages for better summary generation
                    message_role = entry.get("message", {}).get("role")
                    if message_role == "user":
                        content = entry["message"].get("content", "")
                        if isinstance(content, str) and content:
                            session_user_messages[session_id].append(content)
                    elif message_role == "assistant":
                        content = entry["message"].get("content", "")
                        # Extract text from content blocks for assistant messages
                        if isinstance(content, list):
                            text_parts = []
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    text_parts.append(block.get("text", ""))
                            if text_parts:
                                session_assistant_messages[session_id].append(
                                    " ".join(text_parts)
                                )
                        elif isinstance(content, str) and content:
                            session_assistant_messages[session_id].append(content)

                    # Update summary
                    if entry.get("type") == "summary" and entry.get("summary"):
                        session["summary"] = entry["summary"]

                    # Update timestamp
                    if entry.get("timestamp"):
                        if (
                            session["last_activity"] is None
                            or entry["timestamp"] > session["last_activity"]
                        ):
                            session["last_activity"] = entry["timestamp"]

                except json.JSONDecodeError:
                    continue

    # Populate user/assistant messages for ALL sessions
    for session_id, session in sessions.items():
        # Get first 2 meaningful user messages
        first_user_messages = []
        if session_id in session_user_messages:
            user_messages = session_user_messages[session_id]
            for content in user_messages:
                if not _is_system_message(content) and _is_meaningful_message(content):
                    first_user_messages.append(content)
                    if len(first_user_messages) >= 2:
                        break

        # Get last meaningful user message
        last_user_msg = None
        if session_id in session_user_messages:
            user_messages = session_user_messages[session_id]
            for content in reversed(user_messages):
                if not _is_system_message(content) and _is_meaningful_message(content):
                    last_user_msg = content
                    break

        # Get last meaningful assistant message
        last_assistant_msg = None
        if session_id in session_assistant_messages:
            assistant_messages = session_assistant_messages[session_id]
            for content in reversed(assistant_messages):
                if _is_meaningful_message(content):
                    last_assistant_msg = content
                    break

        # Store all messages (no truncation here)
        session["first_user_message"] = (
            first_user_messages[0] if first_user_messages else None
        )
        session["second_user_message"] = (
            first_user_messages[1] if len(first_user_messages) > 1 else None
        )
        session["last_user_message"] = last_user_msg
        session["last_assistant_message"] = last_assistant_msg

        # Generate summary only for sessions without one
        if session["summary"] == "New Session":
            if last_user_msg:
                session["summary"] = last_user_msg
            elif last_assistant_msg:
                session["summary"] = last_assistant_msg

    # Sort by last activity
    result = sorted(
        sessions.values(), key=lambda x: x["last_activity"] or 0, reverse=True
    )

    # Apply pagination
    if limit is not None:
        result = result[offset : offset + limit]

    return result


def get_conversation_id(project_name: str, search_text: str) -> str | None:
    """Find conversation ID by searching summary text

    Args:
        project_name: Encoded project name
        search_text: Text to search in summaries

    Returns:
        First matching conversation ID
    """
    import warnings

    warnings.warn(
        "get_conversation_id() is deprecated, use calmlib.utils.patchbay.search_sessions() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    conversations = list_conversations(project_name)

    for conv in conversations:
        if search_text.lower() in conv["summary"].lower():
            return conv["id"]

    return None


def get_all_messages(
    project_name: str, conversation_id: str, limit: int | None = None
) -> list[dict[str, Any]]:
    """Get all messages in a conversation

    Args:
        project_name: Encoded project name
        conversation_id: Session ID
        limit: Optional limit on number of messages

    Returns:
        List of message entries sorted by timestamp
    """
    import warnings

    warnings.warn(
        "get_all_messages() is deprecated, use claude-agent-sdk get_session_messages() "
        "or calmlib.utils.patchbay instead",
        DeprecationWarning,
        stacklevel=2,
    )
    project_dir = get_claude_home() / "projects" / project_name
    if not project_dir.exists():
        return []

    messages = []

    for jsonl_file in project_dir.glob("*.jsonl"):
        with open(jsonl_file) as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)
                    if entry.get("sessionId") == conversation_id:
                        messages.append(entry)
                except json.JSONDecodeError:
                    continue

    # Sort by timestamp
    messages.sort(key=lambda x: x.get("timestamp", 0))

    # Apply limit if specified
    if limit is not None:
        messages = messages[-limit:]  # Get most recent messages

    return messages


def get_message_content(entry: dict[str, Any]) -> str | None:
    """Extract readable content from a message entry

    Args:
        entry: JSONL entry

    Returns:
        Human-readable message content
    """
    if entry.get("type") == "summary":
        return f"[Summary: {entry.get('summary', '')}]"

    message = entry.get("message", {})
    role = message.get("role", "")
    content = message.get("content", "")

    if isinstance(content, str) and content:
        return f"[{role}] {content}"
    elif isinstance(content, list):
        # Handle content blocks
        text_parts = []
        tool_info = []

        for block in content:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type")

            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "tool_use":
                tool_name = block.get("name", "unknown")
                tool_info.append(f"🔧 {tool_name}")
            elif block_type == "tool_result":
                result_content = block.get("content", "")
                if isinstance(result_content, str):
                    preview = (
                        result_content[:80] + "..."
                        if len(result_content) > 80
                        else result_content
                    )
                    tool_info.append(f"✓ {preview}")

        # Combine text and tool info
        parts = []
        if text_parts:
            parts.append(" ".join(text_parts))
        if tool_info:
            parts.extend(tool_info)

        if parts:
            return f"[{role}] {' | '.join(parts)}"

    # Fallback for other message types
    if role:
        return f"[{role}] (no displayable content)"

    return None


# MongoDB-based conversation management


def get_conversation_metadata(
    conversation_id: str, mongo_uri: str = "mongodb://localhost:27017"
) -> ConversationMetadata | None:
    """Get conversation metadata from MongoDB."""
    _, collection = get_mongo_connection(mongo_uri)
    doc = collection.find_one({"conversation_id": conversation_id})
    if doc:
        doc.pop("_id", None)
        return ConversationMetadata(**doc)
    return None


def save_conversation_metadata(
    metadata: ConversationMetadata, mongo_uri: str = "mongodb://localhost:27017"
) -> None:
    """Save conversation metadata to MongoDB."""
    _, collection = get_mongo_connection(mongo_uri)
    collection.update_one(
        {"conversation_id": metadata.conversation_id},
        {"$set": metadata.model_dump()},
        upsert=True,
    )


def dismiss_conversation(
    conversation_id: str, mongo_uri: str = "mongodb://localhost:27017"
) -> None:
    """Mark a conversation as dismissed."""
    metadata = get_conversation_metadata(conversation_id, mongo_uri)
    if not metadata:
        metadata = ConversationMetadata(conversation_id=conversation_id, dismissed=True)
    else:
        metadata.dismissed = True
    save_conversation_metadata(metadata, mongo_uri)


def undismiss_conversation(
    conversation_id: str, mongo_uri: str = "mongodb://localhost:27017"
) -> None:
    """Remove a conversation from dismissed list.

    Args:
        conversation_id: Conversation ID to undismiss
        mongo_uri: MongoDB connection string
    """
    metadata = get_conversation_metadata(conversation_id, mongo_uri)
    if metadata:
        metadata.dismissed = False
        save_conversation_metadata(metadata, mongo_uri)


def find_conversation_by_prefix(prefix: str) -> tuple[str, str, str, str] | None:
    """Find conversation by ID prefix.

    Args:
        prefix: Conversation ID prefix (first 8-12 chars)

    Returns:
        Tuple of (full_conversation_id, project_name, project_path, summary) or None if not found

    Raises:
        ValueError: If prefix matches multiple conversations (ambiguous)
    """
    import warnings

    warnings.warn(
        "find_conversation_by_prefix() is deprecated, use calmlib.utils.patchbay.get_session() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    projects = list_projects(include_stats=False)
    matches = []

    for project in projects:
        conversations = list_conversations(project["name"])
        for conv in conversations:
            if conv["id"].startswith(prefix):
                matches.append(
                    (
                        conv["id"],
                        project["name"],
                        project.get("full_path", ""),
                        conv["summary"],
                    )
                )

    if len(matches) == 0:
        return None
    elif len(matches) == 1:
        return matches[0]
    else:
        # Multiple matches - ambiguous
        raise ValueError(
            f"Ambiguous prefix '{prefix}' matches {len(matches)} conversations. "
            f"Please provide more characters."
        )
