"""Varied title styling for patchbay sessions.

Generates visually distinct titles using LLM with configurable style parameters.
None = randomize (pure random or date-seeded).
"""

from __future__ import annotations

import random
import time
from datetime import date
from enum import Enum
from typing import Optional

from loguru import logger
from pydantic import BaseModel


class Capitalization(str, Enum):
    title = "title"           # Every Word Capitalized
    sentence = "sentence"     # Only first word
    lower = "lower"           # all lowercase


class Length(str, Enum):
    short = "short"   # 1-4 words
    med = "med"       # 3-6 words
    long = "long"     # 5-8 words


class Vocabulary(str, Enum):
    full = "full"         # full descriptive phrases
    frugal = "frugal"     # minimal, noun/verb only
    caveman = "caveman"   # telegraphic, terse shortlog


LENGTH_RANGES = {
    Length.short: (1, 4),
    Length.med: (3, 6),
    Length.long: (5, 8),
}

# Activation rates for random mode
RANDOM_WEIGHTS = {
    "emoji": 0.20,       # emoji is rare — 20%
    "quotes": 0.25,      # quotes sometimes — 25%
}


class TitleStyleConfig(BaseModel):
    emoji: Optional[bool] = None
    capitalization: Optional[Capitalization] = None
    length: Optional[Length] = None
    quotes: Optional[bool] = None       # None = maybe, if a good term exists
    vocabulary: Optional[Vocabulary] = None

    def resolve(self, seed: str | None = None) -> TitleStyleConfig:
        """Fill None fields with random values. Seed for reproducibility."""
        rng = random.Random(seed)

        return TitleStyleConfig(
            emoji=self.emoji if self.emoji is not None else rng.random() < RANDOM_WEIGHTS["emoji"],
            capitalization=self.capitalization or rng.choice(list(Capitalization)),
            length=self.length or rng.choice(list(Length)),
            quotes=self.quotes if self.quotes is not None else rng.random() < RANDOM_WEIGHTS["quotes"],
            vocabulary=self.vocabulary or rng.choice(list(Vocabulary)),
        )


def _date_seed() -> str:
    return date.today().isoformat()


def _build_prompt(description: str, config: TitleStyleConfig) -> str:
    length_range = LENGTH_RANGES[config.length]
    parts = [
        "Generate a short title for this AI coding session.",
        f"Session description: {description}",
        "",
        "Style rules (follow ALL of them):",
        f"- Word count: {length_range[0]}-{length_range[1]} words",
        f"- Capitalization: {config.capitalization.value}",
    ]

    if config.vocabulary == Vocabulary.full:
        parts.append("- Vocabulary: full descriptive phrases")
    elif config.vocabulary == Vocabulary.frugal:
        parts.append("- Vocabulary: minimal — nouns and verbs only, drop articles/prepositions")
    elif config.vocabulary == Vocabulary.caveman:
        parts.append("- Vocabulary: telegraphic, terse, like a git commit shortlog")

    parts.append("- NEVER use ALL CAPS for the whole title")

    if config.emoji:
        parts.append("- Start with ONE emoji that is THEMATICALLY RELEVANT to the task content")
        parts.append("  (e.g. 🔍 for search, 🧹 for cleanup, 📥 for ingestion — NOT random decorative emoji)")
    else:
        parts.append("- NO emoji")

    if config.quotes:
        parts.append("- Wrap ONE key technical term in single quotes — a command name, feature name, or concept")
        parts.append("  (e.g. 'task add', 'ingest', 'dedup' — NOT the project name)")
        parts.append("  If no clear technical term fits, skip quotes entirely")
    else:
        parts.append("- No quotes around terms")

    parts.extend([
        "",
        "IMPORTANT:",
        "- Do NOT include the project name (e.g. 'plaintask') in the title",
        "- Only mention a sub-component (cli, tui, tests) if the task is specifically about that component",
        "- Keep language natural and professional — no weird phrasings",
        "- The title should describe WHAT is being done, not the project",
        "",
        "Reply with ONLY the title. No explanation, no quotes around the whole thing.",
    ])

    return "\n".join(parts)


def _validate_title(title: str, config: TitleStyleConfig) -> list[str]:
    """Check that easily verifiable criteria are met. Returns list of violations."""
    violations = []
    length_range = LENGTH_RANGES[config.length]

    words = title.split()
    # Don't count emoji as a word
    words_no_emoji = [w for w in words if not any(ord(c) > 0x1F000 for c in w)]
    wc = len(words_no_emoji)

    if wc < length_range[0]:
        violations.append(f"too short: {wc} words (min {length_range[0]})")
    if wc > length_range[1]:
        violations.append(f"too long: {wc} words (max {length_range[1]})")

    has_emoji = any(ord(c) > 0x1F000 for c in title)
    if config.emoji and not has_emoji:
        violations.append("missing emoji")
    if not config.emoji and has_emoji:
        violations.append("unexpected emoji")

    # Check for ALL CAPS (more than 2 consecutive uppercase words)
    upper_words = [w for w in words_no_emoji if w.isupper() and len(w) > 1]
    if len(upper_words) > 2:
        violations.append("too many ALL CAPS words")

    return violations


def generate_styled_title(
    description: str,
    config: TitleStyleConfig | None = None,
    seed: str | None = "date",
    max_retries: int = 1,
    model: str | None = None,
    size: str = "small",
) -> str:
    """Generate a styled title for a session.

    Retry policy: up to `max_retries + 1` attempts at `size`. If the last
    attempt is still invalid OR returns empty, fall back once to `size="med"`
    (cloud haiku) regardless of the `size` argument, since a slow local model
    that keeps failing validation is not worth retrying further.

    Args:
        description: raw session description / first message
        config: style config (None = all random)
        seed: "date" for date-seeded, None for pure random, or custom string
        model: model shortname for calmlib.llm (overrides size if set)
        size: model size tier — "small" uses Jan local, "med"/"big" for cloud
    """
    from calmlib.llm import query_llm_text

    if config is None:
        config = TitleStyleConfig()

    actual_seed = _date_seed() if seed == "date" else seed
    resolved = config.resolve(seed=actual_seed)

    base_prompt = _build_prompt(description, resolved)
    prompt = base_prompt

    def _try(call_size: str | None, call_model: str | None, attempt_label: str) -> tuple[str, list[str], float]:
        t0 = time.monotonic()
        raw = query_llm_text(prompt, model=call_model, size=call_size, temperature=0.7)
        elapsed = time.monotonic() - t0
        t = (raw or "").strip()
        if t.startswith('"') and t.endswith('"'):
            t = t[1:-1]
        v = _validate_title(t, resolved) if t else ["empty response"]
        logger.debug(
            f"Title attempt {attempt_label} ({call_model or call_size}) took {elapsed:.1f}s — "
            f"raw={raw!r} → {t!r} violations={v}"
        )
        return t, v, elapsed

    title = ""
    for attempt in range(max_retries + 1):
        title, violations, elapsed = _try(
            call_size=size if not model else None,
            call_model=model,
            attempt_label=f"{attempt + 1}/{max_retries + 1}",
        )
        if not violations:
            logger.debug(f"Title generated (attempt {attempt + 1}, {elapsed:.1f}s): {title}")
            return title
        logger.warning(
            f"Title attempt {attempt + 1}/{max_retries + 1} failed ({elapsed:.1f}s) "
            f"model={model or size} violations={violations} raw={title!r}"
        )
        prompt = base_prompt + f"\n\nPrevious attempt failed validation: {violations}. Try again."

    # Fallback: all retries failed → try once with a cloud model before giving up.
    if size == "small" and model is None:
        prompt = base_prompt
        logger.warning(
            f"Small model failed {max_retries + 1}× — falling back to size='med' for a final attempt"
        )
        fb_title, fb_violations, fb_elapsed = _try(
            call_size="med", call_model=None, attempt_label="fallback"
        )
        if not fb_violations:
            logger.info(f"Title generated via fallback ({fb_elapsed:.1f}s): {fb_title}")
            return fb_title
        logger.warning(
            f"Fallback also failed ({fb_elapsed:.1f}s) violations={fb_violations} raw={fb_title!r}"
        )
        if fb_title:
            title = fb_title

    logger.warning(
        f"Title validation failed after all attempts, using last result: {title!r}"
    )
    return title
