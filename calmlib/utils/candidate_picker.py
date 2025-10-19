"""
Advanced candidate picker with fuzzy matching and user interaction

Implements sophisticated matching logic similar to modern CLI tools:
1. Exact match
2. Prefix match (tab-completion style)
3. Substring match
4. Fuzzy match
5. Interactive selection if multiple candidates
"""

from collections.abc import Callable
from typing import Any

from loguru import logger


def pick_candidate(
    query: str,
    candidates: list[str] | list[list[str]],
    extract_key: Callable[[Any], str] | None = None,
    case_sensitive: bool = False,
    ask_user: bool = True,
) -> Any | None | list[Any]:
    """Pick best candidate using layered matching logic

    Args:
        query: Search query
        candidates: List of candidates (strings) or list of [key, value] pairs
        extract_key: Function to extract search key from candidate (for objects)
        case_sensitive: Whether matching is case-sensitive
        ask_user: If True, ask user to pick when multiple matches; if False, return list

    Returns:
        - If single match: the matching candidate
        - If multiple matches and ask_user=True: user-selected candidate or None
        - If multiple matches and ask_user=False: list of matching candidates
        - If no match: None (or empty list if ask_user=False)

    Examples:
        # Simple strings
        >>> pick_candidate("git", ["git_sync", "github", "gitlab"])
        "git_sync"  # prefix match

        # Return multiple matches
        >>> pick_candidate("git", ["git_sync", "github"], ask_user=False)
        ["git_sync", "github"]  # both have prefix

        # Objects with extract function
        >>> projects = [{"id": "bot", "path": "/path"}]
        >>> pick_candidate("bot", projects, extract_key=lambda p: p["id"])
        {"id": "bot", "path": "/path"}
    """
    if not candidates:
        return None if ask_user else []

    # Normalize query
    search_query = query if case_sensitive else query.lower()

    # Determine candidate type and create searchable list
    is_paired = isinstance(candidates[0], (list, tuple)) and len(candidates[0]) >= 2

    def get_search_key(candidate):
        if extract_key:
            return extract_key(candidate)
        elif is_paired:
            return candidate[0]
        else:
            return candidate

    # Normalize candidates
    searchable = []
    for idx, candidate in enumerate(candidates):
        key = get_search_key(candidate)
        normalized_key = key if case_sensitive else key.lower()
        searchable.append((normalized_key, key, candidate, idx))

    # Layer 1: Exact match
    exact_matches = [c for nkey, key, c, idx in searchable if nkey == search_query]
    if len(exact_matches) == 1:
        logger.debug(f"Exact match: {get_search_key(exact_matches[0])}")
        return exact_matches[0]
    elif len(exact_matches) > 1:
        logger.debug(f"Multiple exact matches: {len(exact_matches)}")
        if ask_user:
            return _ask_user_to_pick(exact_matches, get_search_key)
        else:
            return exact_matches

    # Layer 2: Prefix match (tab-completion style)
    prefix_matches = [
        c for nkey, key, c, idx in searchable if nkey.startswith(search_query)
    ]
    if len(prefix_matches) == 1:
        logger.debug(f"Prefix match: {get_search_key(prefix_matches[0])}")
        return prefix_matches[0]
    elif len(prefix_matches) > 1:
        # Check if we can narrow down with next character
        # (simulating smart tab completion)
        common_prefix = _find_common_prefix([get_search_key(c) for c in prefix_matches])
        if len(common_prefix) > len(search_query):
            logger.debug(f"Ambiguous prefix, common: {common_prefix}")
        logger.debug(f"Multiple prefix matches: {len(prefix_matches)}")
        if ask_user:
            return _ask_user_to_pick(prefix_matches, get_search_key)
        else:
            return prefix_matches

    # Layer 3: Substring match (anywhere in the string)
    substring_matches = [c for nkey, key, c, idx in searchable if search_query in nkey]
    if len(substring_matches) == 1:
        logger.debug(f"Substring match: {get_search_key(substring_matches[0])}")
        return substring_matches[0]
    elif len(substring_matches) > 1:
        logger.debug(f"Multiple substring matches: {len(substring_matches)}")
        if ask_user:
            return _ask_user_to_pick(substring_matches, get_search_key)
        else:
            return substring_matches

    # No matches found
    logger.debug(f"No matches found for: {query}")
    return None if ask_user else []


def _find_common_prefix(strings: list[str]) -> str:
    """Find common prefix among strings (case-insensitive)"""
    if not strings:
        return ""

    strings = [s.lower() for s in strings]
    prefix = strings[0]

    for s in strings[1:]:
        while not s.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""

    return prefix


def _ask_user_to_pick(candidates: list[Any], get_key: Callable) -> Any | None:
    """Ask user to select from multiple candidates

    Uses calmlib.utils.user_interactions.ask_user_choice for interactive selection
    """
    import asyncio

    from calmlib.utils.user_interactions import ask_user_choice

    # Format choices
    choices = [get_key(c) for c in candidates]

    # Run async function
    result = asyncio.run(
        ask_user_choice(
            question="Multiple matches found. Select one:",
            choices=choices,
        )
    )

    if result is None:
        return None

    # Find matching candidate
    for candidate in candidates:
        if get_key(candidate) == result:
            return candidate

    return None
