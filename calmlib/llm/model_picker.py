"""
LLM utilities for model selection and API key management.
"""

import os
from enum import Enum

from loguru import logger


class ModelSize(str, Enum):
    """Size tiers for model selection."""

    small = "small"  # haiku → fallback openai mini
    med = "med"  # haiku / flash
    big = "big"  # sonnet / opus


# Provider to API key mapping
PROVIDER_API_KEYS = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY"],
    "xai": ["XAI_API_KEY"],
    "jan": [],  # Local Jan app — no API key needed
    "ollama": [],  # Local models don't need API keys
}

# Default models for each provider (ordered by preference)
PROVIDER_DEFAULT_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
    "anthropic": ["claude-4", "claude-3.7", "claude-3.5-sonnet", "claude-3.5-haiku"],
    "google": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0"],
    "xai": ["grok-3", "grok-3-mini", "grok-2"],
    "jan": ["jan-local"],  # Auto-discovered from Jan API
    "ollama": ["llama3-8b", "qwen-7b", "gemma2-9b"],
}

# Flip to True to re-enable jan-local / ollama LLM paths. Both are gated
# independently so you can re-enable just one. Default SIZE_MODEL_MAP below
# routes "small" to cloud haiku — set primary to "jan-local" if you flip
# JAN_ENABLED back on. See memory: feedback_block_local_models.
JAN_ENABLED = False
OLLAMA_ENABLED = False

# Size-based model preferences: (primary, fallback)
# `small` historically routed to ("jan-local", "claude-4.5-haiku"). Switched
# to cloud-only after laptop overheating incident — restore the old tuple if
# JAN_ENABLED is flipped back on.
SIZE_MODEL_MAP = {
    ModelSize.small: ("claude-4.5-haiku", "gpt-4.1-mini"),
    ModelSize.med: ("claude-4.5-haiku", "gemini-2.5-flash"),
    ModelSize.big: ("claude-4-sonnet", "gpt-4o"),
}

# Local-provider model shortcuts. Calling code that passes any of these
# explicitly is gated by JAN_ENABLED / OLLAMA_ENABLED.
JAN_MODEL_SHORTCUTS: frozenset[str] = frozenset({"jan-local"})
OLLAMA_MODEL_SHORTCUTS: frozenset[str] = frozenset(
    {
        "qwen-7b",
        "qwen-3b",
        "qwen-14b",
        "llama3-8b",
        "llama3-1b",
        "gemma2-2b",
        "gemma2-9b",
        "deepseek-r1",
    }
)


def _provider_of(model: str) -> str | None:
    """Return the provider segment of `model` (handles full names and shortcuts)."""
    if "/" in model:
        return model.split("/", 1)[0]
    if model in JAN_MODEL_SHORTCUTS:
        return "jan"
    if model in OLLAMA_MODEL_SHORTCUTS:
        return "ollama"
    return None


def assert_model_provider_enabled(model: str) -> None:
    """Raise if `model` routes to a disabled local provider.

    Defaults never resolve to a local provider, so this guard only fires when
    a caller passes `model=` explicitly. See memory: feedback_block_local_models.
    """
    provider = _provider_of(model)
    if provider == "jan" and not JAN_ENABLED:
        raise RuntimeError(
            f"calmlib LLM model {model!r} routes through Jan, which is disabled "
            "(JAN_ENABLED=False in calmlib/llm/model_picker.py) — local model "
            "paths cause laptop overheating. Switch to a cloud model or flip "
            "the flag to re-enable. See memory: feedback_block_local_models."
        )
    if provider == "ollama" and not OLLAMA_ENABLED:
        raise RuntimeError(
            f"calmlib LLM model {model!r} routes through Ollama, which is "
            "disabled (OLLAMA_ENABLED=False in calmlib/llm/model_picker.py) — "
            "local model paths cause laptop overheating. Switch to a cloud "
            "model or flip the flag to re-enable. "
            "See memory: feedback_block_local_models."
        )

# Jan app configuration
JAN_API_BASE = os.getenv("JAN_API_BASE", "http://localhost:1337/v1")
JAN_MODEL_NAME = os.getenv("JAN_MODEL_NAME", "")  # Auto-discovered if empty

# Model to provider mapping (extracted from MODEL_NAME_SHORTCUTS)
MODEL_TO_PROVIDER = {
    # Anthropic models
    "claude-3-5-haiku": "anthropic",
    "claude-3-5-sonnet": "anthropic",
    "claude-3-7": "anthropic",
    "claude-3.5-haiku": "anthropic",
    "claude-3.5-sonnet": "anthropic",
    "claude-3.7": "anthropic",
    "claude-4": "anthropic",
    "claude-4-opus": "anthropic",
    "claude-4-sonnet": "anthropic",
    "claude-4.1-opus": "anthropic",
    # OpenAI models
    "gpt-4o-mini": "openai",
    "o4-mini": "openai",
    "gpt-4.1-nano": "openai",
    "gpt-4.1-mini": "openai",
    "gpt-4o": "openai",
    "gpt-4.1": "openai",
    "o3": "openai",
    "gpt-4": "openai",
    "o1-pro": "openai",
    "o1": "openai",
    "o1-mini": "openai",
    "o1-preview": "openai",
    "o3-mini": "openai",
    "gpt-4-turbo": "openai",
    "gpt-4.5": "openai",
    "gpt-4.5-preview": "openai",
    # Google models
    "gemini-2.5-flash": "google",
    "gemini-2.5-pro": "google",
    "gemini-2.5-exp": "google",
    "gemini-2.0": "google",
    "gemini-2.0-flash": "google",
    "gemini-2.0-flash-exp": "google",
    "gemini-2.5-max": "google",
    "gemini-exp-1206": "google",
    # xAI models
    "grok-2": "xai",
    "grok-3-mini": "xai",
    "grok-3": "xai",
    # Cursor models
    "cursor-fast": "cursor",
    "cursor-small": "cursor",
    # Deepseek models
    "deepseek-r1": "deepseek",
    "deepseek-v3": "deepseek",
    # Jan models (local)
    "jan-local": "jan",
    # Ollama models
    "qwen-7b": "ollama",
    "qwen-3b": "ollama",
    "qwen-14b": "ollama",
    "llama3-8b": "ollama",
    "llama3-1b": "ollama",
    "gemma2-2b": "ollama",
    "gemma2-9b": "ollama",
}


def get_available_providers() -> dict[str, bool]:
    """
    Check which LLM providers have API keys available.

    Returns:
        Dict mapping provider name to whether API key is available
    """
    available = {}

    for provider, key_names in PROVIDER_API_KEYS.items():
        if provider == "ollama":
            # Ollama is always available (local)
            available[provider] = True
            continue

        has_key = False
        for key_name in key_names:
            if os.getenv(key_name):
                has_key = True
                break
        available[provider] = has_key

    return available


def get_provider_for_model(model: str) -> str | None:
    """
    Get the provider name for a given model.

    Args:
        model: Model name (can be shortcut or full name)

    Returns:
        Provider name or None if unknown
    """
    # Handle full model names like "anthropic/claude-3-5-sonnet"
    if "/" in model:
        return model.split("/")[0]

    # Handle shortcuts
    return MODEL_TO_PROVIDER.get(model)


def select_available_model(
    preferred_model: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Select an available model based on API keys.

    Args:
        preferred_model: Model to prefer if its provider has API key

    Returns:
        Tuple of (selected_model, reason) or (None, error_reason)
    """
    available_providers = get_available_providers()
    available_list = [p for p, avail in available_providers.items() if avail]

    if not available_list:
        return None, "No API keys found for any LLM provider"

    # If preferred model is specified, check if its provider is available
    if preferred_model:
        provider = get_provider_for_model(preferred_model)
        if provider and available_providers.get(provider, False):
            return preferred_model, f"Using preferred model {preferred_model}"

    # Select a provider with available API key (prefer non-ollama if available)
    cloud_providers = [p for p in available_list if p != "ollama"]
    if cloud_providers:
        selected_provider = cloud_providers[0]  # Take first available cloud provider
    else:
        selected_provider = available_list[
            0
        ]  # Fall back to any available (likely ollama)

    # Get the best model for this provider
    default_models = PROVIDER_DEFAULT_MODELS.get(selected_provider, [])
    if default_models:
        selected_model = default_models[0]
        reason = f"Auto-selected {selected_model} (provider: {selected_provider}) based on available API keys"
        return selected_model, reason

    return None, f"No default models configured for provider {selected_provider}"


def get_fallback_model(failed_model: str) -> tuple[str | None, str | None]:
    """
    Get a fallback model when the original fails due to API key issues.

    Args:
        failed_model: The model that failed

    Returns:
        Tuple of (fallback_model, reason) or (None, error_reason)
    """
    failed_provider = get_provider_for_model(failed_model)
    available_providers = get_available_providers()

    # Find providers that are available and different from the failed one
    fallback_providers = [
        p for p, avail in available_providers.items() if avail and p != failed_provider
    ]

    if not fallback_providers:
        return (
            None,
            f"No fallback providers available (failed provider: {failed_provider})",
        )

    # Prefer cloud providers over ollama for fallbacks
    cloud_providers = [p for p in fallback_providers if p != "ollama"]
    if cloud_providers:
        selected_provider = cloud_providers[0]
    else:
        selected_provider = fallback_providers[0]

    # Get the best model for the fallback provider
    default_models = PROVIDER_DEFAULT_MODELS.get(selected_provider, [])
    if default_models:
        fallback_model = default_models[0]
        reason = f"Falling back to {fallback_model} (provider: {selected_provider}) due to {failed_model} API key error"
        return fallback_model, reason

    return (
        None,
        f"No default models configured for fallback provider {selected_provider}",
    )


def is_jan_available() -> bool:
    """Check if Jan app API is reachable."""
    if not JAN_ENABLED:
        return False
    try:
        import httpx

        resp = httpx.get(f"{JAN_API_BASE}/models", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


_jan_model_cache: str | None = None


def discover_jan_model() -> str | None:
    """Discover the first available model from Jan's /models endpoint.

    Caches the result in-memory after first successful call.
    """
    global _jan_model_cache
    if not JAN_ENABLED:
        return None
    if _jan_model_cache is not None:
        return _jan_model_cache

    # Env override
    env_model = os.getenv("JAN_MODEL_NAME", "")
    if env_model:
        _jan_model_cache = env_model
        return env_model

    try:
        import httpx

        resp = httpx.get(f"{JAN_API_BASE}/models", timeout=2.0)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                _jan_model_cache = data[0]["id"]
                logger.debug(f"Jan model discovered: {_jan_model_cache}")
                return _jan_model_cache
    except Exception as e:
        logger.debug(f"Jan model discovery failed: {e}")

    return None


def get_model_by_size(size: str | ModelSize) -> tuple[str, dict]:
    """Select a model based on size tier.

    Args:
        size: "small", "med", or "big"

    Returns:
        Tuple of (model_name, extra_kwargs) where extra_kwargs may contain
        api_base for local models.
    """
    size = ModelSize(size)
    primary, fallback = SIZE_MODEL_MAP[size]

    if primary == "jan-local":
        # Gated by JAN_ENABLED — both is_jan_available() and discover_jan_model()
        # short-circuit to False/None when the flag is off.
        jan_model = discover_jan_model()
        if jan_model and is_jan_available():
            logger.debug(f"Using Jan local model: {jan_model}")
            return "jan-local", {}
        logger.warning(f"Jan not available, falling back to {fallback}")
        return fallback, {}

    return primary, {}


def is_api_key_error(error: Exception) -> bool:
    """
    Check if an error is related to API key issues.

    Args:
        error: Exception to check

    Returns:
        True if this looks like an API key error
    """
    error_str = str(error).lower()
    api_key_indicators = [
        "api key",
        "api_key",
        "authentication",
        "unauthorized",
        "invalid key",
        "missing key",
        "401",
        "403",
        "authentication failed",
        "invalid api key",
    ]

    return any(indicator in error_str for indicator in api_key_indicators)
