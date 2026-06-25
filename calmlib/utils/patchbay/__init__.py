"""Patchbay — query, navigate, and coordinate AI coding sessions."""

from calmlib.utils.patchbay.session import PatchbaySession
from calmlib.utils.patchbay.resume import resume_session, fork_session
from calmlib.utils.patchbay.scenario import run_scenario, ScenarioResult, StepResult
from calmlib.utils.patchbay.digest import get_session_digest, DigestMode, SessionDigest
from calmlib.utils.patchbay.core.models import SessionInfo, Topics
from calmlib.utils.patchbay.core.db import get_collection, get_empty_collection
from calmlib.utils.patchbay.core.refresh import (
    get_claude_name_fields,
    generate_topics,
    refresh_session_metadata,
    bulk_refresh_metadata,
    cleanup_empty_sessions,
    sweep_empty_sessions,
    resurrect_sessions,
)
from calmlib.utils.patchbay.core.search import (
    set_session_title,
    search_sessions,
    semantic_search_sessions,
    list_sessions,
    count_sessions,
    get_session,
    get_session_summary,
    link_session,
    tag_session,
    update_session_status,
    launch_session,
    fav_session,
    unfav_session,
    find_session_by_title,
    find_current_session,
    list_fav_sessions,
    list_unlinked_sessions,
)

__all__ = [
    "PatchbaySession",
    "resume_session",
    "fork_session",
    "run_scenario",
    "ScenarioResult",
    "StepResult",
    "SessionInfo",
    "Topics",
    "get_collection",
    "get_empty_collection",
    "get_claude_name_fields",
    "generate_topics",
    "refresh_session_metadata",
    "bulk_refresh_metadata",
    "cleanup_empty_sessions",
    "sweep_empty_sessions",
    "resurrect_sessions",
    "set_session_title",
    "search_sessions",
    "semantic_search_sessions",
    "list_sessions",
    "count_sessions",
    "get_session",
    "get_session_summary",
    "link_session",
    "tag_session",
    "update_session_status",
    "launch_session",
    "fav_session",
    "unfav_session",
    "find_session_by_title",
    "find_current_session",
    "list_fav_sessions",
    "list_unlinked_sessions",
]
