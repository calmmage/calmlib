"""Patchbay query layer — re-exports from core/ subpackage.

All implementation lives in core/. This module exists for backward compatibility.
"""

# Models
from calmlib.utils.patchbay.core.models import SessionInfo, Topics  # noqa: F401

# DB
from calmlib.utils.patchbay.core.db import (  # noqa: F401
    get_collection,
    get_empty_collection,
    _find_session_doc,
    _doc_to_session,
    _find_claude_conversation_jsonl,
)

# Refresh
from calmlib.utils.patchbay.core.refresh import (  # noqa: F401
    get_claude_name_fields,
    generate_topics,
    refresh_session_metadata,
    bulk_refresh_metadata,
    cleanup_empty_sessions,
    sweep_empty_sessions,
    resurrect_sessions,
    _normalize_session_title,
    _count_real_user_messages,
    _extract_claude_name_fields,
    _extract_session_model,
    _get_jsonl_mtime,
    _build_title_description,
    AI_MODEL_PREFIXES,
    EXIT_PHRASES,
)

# Search & ops
from calmlib.utils.patchbay.core.search import (  # noqa: F401
    search_sessions,
    list_sessions,
    count_sessions,
    get_session,
    get_session_summary,
    link_session,
    tag_session,
    update_session_status,
    fav_session,
    unfav_session,
    find_session_by_title,
    find_current_session,
    list_fav_sessions,
    set_session_title,
    launch_session,
    list_unlinked_sessions,
)
