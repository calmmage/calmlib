"""
LLM utilities for model selection and API key management.
"""

import os

# Provider to API key mapping
PROVIDER_API_KEYS = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_AI_API_KEY"],
    "xai": ["XAI_API_KEY"],
    "ollama": [],  # Local models don't need API keys
}

# Default models for each provider (ordered by preference)
PROVIDER_DEFAULT_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
    "anthropic": ["claude-4", "claude-3.7", "claude-3.5-sonnet", "claude-3.5-haiku"],
    "google": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0"],
    "xai": ["grok-3", "grok-3-mini", "grok-2"],
    "ollama": ["llama3-8b", "qwen-7b", "gemma2-9b"],
}

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
