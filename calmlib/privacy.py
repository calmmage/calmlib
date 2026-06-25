"""Secret-shape redactor — strip obvious credentials from text before egress.

Use this whenever text of unknown provenance is about to leave the process:
- arguments to LLM API calls (OpenAI, Anthropic, etc.)
- log lines that may include user input or file contents
- payloads to external services (gist, pastebin, slack, telegram)
- snapshots written to disk for sharing or upload

Best-effort, not a security guarantee. Pair with source-level opt-outs
(skip-folders, label-based filters) for content you actively want kept off
external services. Tuned conservatively so prose like "password: forgot it"
is not redacted — minimum credential lengths apply.

API:
    from calmlib.privacy import redact, redact_text, has_secrets

    redact(text)     -> (scrubbed, {kind: count, ...})  # full info
    redact_text(text) -> scrubbed                       # convenience
    has_secrets(text) -> bool                           # pre-check

Idempotent: re-running on already-redacted text is a no-op since the
`[REDACTED:<kind>]` placeholders don't match any patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class _Pattern:
    name: str
    regex: re.Pattern
    replace_with: str  # the substring inserted in place of the match


# Order matters: longer/more-specific patterns first so e.g. `sk-ant-...`
# isn't shadowed by the broader `sk-...` rule.
PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        "private_key_block",
        re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----"),
        "[REDACTED:private-key]",
    ),
    _Pattern(
        "anthropic_key",
        re.compile(r"sk-ant-[A-Za-z0-9_\-]{40,}"),
        "[REDACTED:anthropic-key]",
    ),
    _Pattern(
        "openai_key",
        re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),
        "[REDACTED:openai-key]",
    ),
    _Pattern(
        "stripe_live_key",
        re.compile(r"\b[ps]k_live_[A-Za-z0-9]{20,}\b"),
        "[REDACTED:stripe-key]",
    ),
    _Pattern(
        "github_token",
        re.compile(r"\bgh[opsur]_[A-Za-z0-9]{20,}\b"),
        "[REDACTED:github-token]",
    ),
    _Pattern(
        "slack_token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
        "[REDACTED:slack-token]",
    ),
    _Pattern(
        "aws_access_key_id",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED:aws-access-key]",
    ),
    _Pattern(
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
        "[REDACTED:jwt]",
    ),
    _Pattern(
        "bearer_header",
        re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b"),
        "Bearer [REDACTED:token]",
    ),
)


# Keyword-anchored patterns where we redact *only the value*, not the keyword,
# so `password: hunter2longpass` becomes `password: [REDACTED:password]`. The
# 12-char minimum dramatically reduces false positives on prose like
# `password: forgot it`.
_KEYWORD_ASSIGN: tuple[tuple[str, re.Pattern, str], ...] = (
    (
        "password",
        re.compile(r"""(?ix)
            \b(password|passwd|pwd)\s*[:=]\s*['"]?
            ([^\s'"\n]{12,})
        """),
        "[REDACTED:password]",
    ),
    (
        "api_key",
        re.compile(r"""(?ix)
            \b(api[_\-]?key|secret[_\-]?key|access[_\-]?token|auth[_\-]?token)\s*[:=]\s*['"]?
            ([A-Za-z0-9_\-]{16,})
        """),
        "[REDACTED:api-key]",
    ),
)

# DB connection strings of the form `scheme://user:PASSWORD@host`. We replace
# only the password portion, keeping scheme/user/host intact for retrieval.
_DB_URL = re.compile(
    r"\b(?P<scheme>postgres(?:ql)?|mysql|mongodb)(?P<sub>\+[a-z]+)?://(?P<user>[^:/@\s]+):(?P<pwd>[^@\s]+)@"
)


def redact(text: str) -> tuple[str, dict[str, int]]:
    """Replace credential-shaped substrings with `[REDACTED:<kind>]` tags.

    Returns the scrubbed text and a per-kind hit count. Empty count dict means
    the input was clean. Idempotent.
    """
    if not text:
        return text or "", {}

    counts: dict[str, int] = {}

    for p in PATTERNS:
        new_text, n = p.regex.subn(p.replace_with, text)
        if n:
            counts[p.name] = counts.get(p.name, 0) + n
            text = new_text

    for name, regex, tag in _KEYWORD_ASSIGN:
        def _sub(m: re.Match, _tag=tag) -> str:
            return f"{m.group(1)}: {_tag}"

        new_text, n = regex.subn(_sub, text)
        if n:
            counts[name] = counts.get(name, 0) + n
            text = new_text

    def _db_sub(m: re.Match) -> str:
        scheme = m.group("scheme") + (m.group("sub") or "")
        return f"{scheme}://{m.group('user')}:[REDACTED:db-password]@"

    new_text, n = _DB_URL.subn(_db_sub, text)
    if n:
        counts["db_url_password"] = counts.get("db_url_password", 0) + n
        text = new_text

    return text, counts


def redact_text(text: str) -> str:
    """Convenience: return only the scrubbed text. Drop the hit counts.

    Use this when you don't care about audit info — just want safe text out.
    """
    out, _ = redact(text)
    return out


def has_secrets(text: str) -> bool:
    """Cheap pre-check: does this text look like it contains a credential?"""
    _, counts = redact(text)
    return bool(counts)


__all__ = ["redact", "redact_text", "has_secrets", "PATTERNS"]
