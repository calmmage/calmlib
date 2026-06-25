"""
Claude Code conversation history utilities

Access and search Claude Code conversation history stored in ~/.claude
"""

from .history import (
    build_project_tree,
    extract_project_directory,
    find_conversation_by_prefix,
    format_project_tree,
    get_all_messages,
    get_claude_home,
    get_conversation_id,
    get_message_content,
    get_project_stats,
    list_conversations,
    list_projects,
)
from .sdk import (
    CLAUDE_CODE_MODEL_SHORTCUTS,
    resolve_claude_code_model,
    start_claude_chat,
)

__all__ = [
    "list_projects",
    "list_conversations",
    "get_conversation_id",
    "get_all_messages",
    "get_message_content",
    "get_project_stats",
    "build_project_tree",
    "format_project_tree",
    "extract_project_directory",
    "find_conversation_by_prefix",
    "get_claude_home",
    "start_claude_chat",
    "resolve_claude_code_model",
    "CLAUDE_CODE_MODEL_SHORTCUTS",
]
