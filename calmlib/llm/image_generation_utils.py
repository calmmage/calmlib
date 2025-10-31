import os
from typing import Any

import litellm
from loguru import logger

# Track messages that should only be logged once
_logged_once: set[str] = set()


def log_once(level: str, message: str, key: str | None = None) -> None:
    """
    Log a message only once per session.

    Args:
        level: Log level ('debug', 'info', 'warning', 'error')
        message: Message to log
        key: Optional unique key for the message. If not provided, message itself is used.
    """
    msg_key = key or message
    if msg_key not in _logged_once:
        _logged_once.add(msg_key)
        log_func = getattr(logger, level.lower())
        log_func(message)

# Explicit model mapping: friendly name -> litellm format
IMAGE_MODELS = {
    # Google Gemini - Conversational (nano banana 🍌)
    # Note: Gemini models use "gemini/" prefix for Gemini API
    "nano-banana": "gemini/gemini-2.5-flash-image",
    "gemini-nano": "gemini/gemini-2.5-flash-image",
    "gemini": "gemini/gemini-2.5-flash-image",
    # Google Imagen - Dedicated image generation
    "imagen-4": "gemini/imagen-4.0-generate-001",
    "imagen-4-fast": "gemini/imagen-4-fast",
    "imagen-4-ultra": "gemini/imagen-4-ultra",
    "imagen": "gemini/imagen-4.0-generate-001",  # default to flagship
    # OpenAI
    "gpt-image-1": "openai/gpt-image-1",
    "gpt-img-1": "openai/gpt-image-1",
    "gpt-1": "openai/gpt-image-1",
    "openai": "openai/gpt-image-1",
    "dalle-3": "openai/dall-e-3",
    "dalle-2": "openai/dall-e-2",
    # Vertex AI (if using Google Cloud)
    "vertex-imagen": "vertex_ai/imagen-4.0-generate-001",
    # AWS Bedrock Stable Diffusion
    "sdxl": "bedrock/stability.stable-diffusion-xl-v0",
    # Recraft
    "recraft": "recraft/recraftv3",
}

# Supported resolutions by vendor
# Format: (width, height) tuples
VENDOR_RESOLUTIONS = {
    "gemini": [
        # Gemini 2.5 Flash Image supports various aspect ratios
        (1024, 1024),  # 1:1 square
        (1152, 896),   # 9:7 landscape
        (896, 1152),   # 7:9 portrait
        (1216, 832),   # 3:2 landscape
        (832, 1216),   # 2:3 portrait
        (1344, 768),   # 7:4 landscape
        (768, 1344),   # 4:7 portrait
        (1536, 640),   # 12:5 landscape
        (640, 1536),   # 5:12 portrait
    ],
    "openai": [
        # DALL-E 3 and GPT Image-1 resolutions
        (1024, 1024),   # square
        (1792, 1024),   # landscape
        (1024, 1792),   # portrait
    ],
    "openai/dall-e-2": [
        # DALL-E 2 only supports square images
        (256, 256),
        (512, 512),
        (1024, 1024),
    ],
    "vertex_ai": [
        # Vertex AI Imagen supports similar to Gemini
        (1024, 1024),  # 1:1 square
        (1152, 896),   # 9:7 landscape
        (896, 1152),   # 7:9 portrait
        (1216, 832),   # 3:2 landscape
        (832, 1216),   # 2:3 portrait
        (1344, 768),   # 7:4 landscape
        (768, 1344),   # 4:7 portrait
        (1536, 640),   # 12:5 landscape
        (640, 1536),   # 5:12 portrait
    ],
    "bedrock": [
        # Stable Diffusion XL resolutions
        (1024, 1024),  # square
        (1152, 896),   # landscape
        (896, 1152),   # portrait
        (1216, 832),   # wide landscape
        (832, 1216),   # tall portrait
        (1344, 768),   # extra wide
        (768, 1344),   # extra tall
        (1536, 640),   # ultra wide
        (640, 1536),   # ultra tall
    ],
    "recraft": [
        # Recraft v3 supports flexible resolutions
        (1024, 1024),   # square
        (1365, 1024),   # landscape
        (1024, 1365),   # portrait
        (1536, 1024),   # wide landscape
        (1024, 1536),   # tall portrait
        (1820, 1024),   # extra wide
        (1024, 1820),   # extra tall
        (1024, 2048),   # ultra tall
        (2048, 1024),   # ultra wide
    ],
}

# Model-specific resolution overrides
MODEL_RESOLUTIONS = {
    "openai/dall-e-2": VENDOR_RESOLUTIONS["openai/dall-e-2"],
    "openai/dall-e-3": VENDOR_RESOLUTIONS["openai"],
    "openai/gpt-image-1": VENDOR_RESOLUTIONS["openai"],
}


def parse_size(size: str) -> tuple[int, int]:
    """
    Parse size string into (width, height) tuple.

    Args:
        size: Size string in format "1024x1024"

    Returns:
        Tuple of (width, height)

    Raises:
        ValueError: If size format is invalid
    """
    try:
        width_str, height_str = size.lower().split("x")
        width = int(width_str)
        height = int(height_str)
        return (width, height)
    except (ValueError, AttributeError) as e:
        raise ValueError(
            f"Invalid size format '{size}'. Expected format: '1024x1024'"
        ) from e


def get_vendor_from_model(model: str) -> str:
    """
    Extract vendor name from full model string.

    Args:
        model: Full model string with vendor prefix (e.g., "gemini/model-name")

    Returns:
        Vendor name (e.g., "gemini", "openai", "vertex_ai", etc.)
    """
    if "/" in model:
        vendor = model.split("/")[0]
        logger.debug(f"Extracted vendor '{vendor}' from model '{model}'")
        return vendor

    logger.debug(f"No vendor prefix found in model '{model}', treating as vendor name")
    return model


def get_supported_resolutions(model: str) -> list[tuple[int, int]]:
    """
    Get supported resolutions for a specific model.

    Args:
        model: Full model string with vendor prefix

    Returns:
        List of supported (width, height) tuples
    """
    logger.debug(f"Looking up supported resolutions for model: {model}")

    # Check model-specific overrides first
    if model in MODEL_RESOLUTIONS:
        resolutions = MODEL_RESOLUTIONS[model]
        logger.debug(f"Found model-specific resolutions: {len(resolutions)} options")
        return resolutions

    # Fall back to vendor resolutions
    vendor = get_vendor_from_model(model)
    if vendor in VENDOR_RESOLUTIONS:
        resolutions = VENDOR_RESOLUTIONS[vendor]
        logger.debug(f"Using vendor resolutions for '{vendor}': {len(resolutions)} options")
        return resolutions

    # No specific resolutions found - allow any
    logger.warning(
        f"No resolution constraints defined for model '{model}' or vendor '{vendor}'. "
        "Any resolution will be allowed."
    )
    return []


def validate_resolution(size: str, model: str) -> None:
    """
    Validate that the requested size is supported by the model.

    Args:
        size: Size string in format "1024x1024"
        model: Full model string with vendor prefix

    Raises:
        ValueError: If the resolution is not supported by the model
    """
    logger.debug(f"Validating resolution '{size}' for model '{model}'")

    # Parse the size
    try:
        requested_resolution = parse_size(size)
        logger.debug(f"Parsed resolution: {requested_resolution}")
    except ValueError as e:
        logger.error(f"Failed to parse size '{size}': {e}")
        raise

    # Get supported resolutions
    supported_resolutions = get_supported_resolutions(model)

    # If no constraints defined, allow any resolution
    if not supported_resolutions:
        logger.debug("No resolution constraints - allowing any resolution")
        return

    # Check if requested resolution is supported
    if requested_resolution not in supported_resolutions:
        vendor = get_vendor_from_model(model)
        supported_str = ", ".join(f"{w}x{h}" for w, h in supported_resolutions)
        error_msg = (
            f"Resolution '{size}' is not supported by model '{model}' (vendor: {vendor}). "
            f"Supported resolutions: {supported_str}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.debug(f"Resolution '{size}' is valid for model '{model}'")


def get_available_api_keys() -> dict[str, bool]:
    """Check which API keys are available in environment."""
    logger.debug("Checking available API keys")

    available = {
        "gemini": bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        ),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "vertex": bool(
            os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            or os.environ.get("VERTEX_PROJECT")
        ),
        "bedrock": bool(
            os.environ.get("AWS_ACCESS_KEY_ID")
            and os.environ.get("AWS_SECRET_ACCESS_KEY")
        ),
        "recraft": bool(os.environ.get("RECRAFT_API_KEY")),
    }

    available_vendors = [k for k, v in available.items() if v]
    logger.debug(f"Available API keys: {available_vendors}")

    return available


def auto_select_model() -> str:
    """
    Auto-select best available model based on API key availability.

    Priority order:
    1. Gemini (nano-banana) - conversational, fast, good quality
    2. OpenAI (gpt-image-1) - industry standard
    3. Raises error if no keys found

    Returns:
        Model name that can be used with generate_image()
    """
    logger.debug("Auto-selecting image generation model based on available API keys")
    available = get_available_api_keys()

    # Priority: Gemini > OpenAI
    if available["gemini"]:
        log_once("info", "Auto-selected vendor: Gemini (nano-banana)", key="vendor:gemini")
        return "nano-banana"

    if available["openai"]:
        log_once("info", "Auto-selected vendor: OpenAI (gpt-image-1)", key="vendor:openai")
        return "gpt-image-1"

    # Fallback checks (less common)
    if available["vertex"]:
        log_once("info", "Auto-selected vendor: Vertex AI (vertex-imagen)", key="vendor:vertex")
        return "vertex-imagen"

    if available["bedrock"]:
        log_once("info", "Auto-selected vendor: AWS Bedrock (sdxl)", key="vendor:bedrock")
        return "sdxl"

    if available["recraft"]:
        log_once("info", "Auto-selected vendor: Recraft (recraftv3)", key="vendor:recraft")
        return "recraft"

    error_msg = (
        "No image generation API keys found. "
        "Please set GEMINI_API_KEY or OPENAI_API_KEY in environment."
    )
    logger.error(error_msg)
    raise ValueError(error_msg)


def resolve_model(model: str | None = None) -> str:
    """
    Resolve a model name to its litellm format.

    Args:
        model: Friendly model name (e.g., "nano-banana", "gpt-1") or None for auto

    Returns:
        Full litellm model string with vendor/ prefix (e.g., "gemini/gemini-2.5-flash-image")
    """
    logger.debug(f"Resolving model: {model}")

    # Auto-select if not provided
    if model is None:
        logger.debug("No model specified, auto-selecting")
        model = auto_select_model()
        logger.debug(f"Auto-selected model: {model}")

    # Look up in mapping
    if model in IMAGE_MODELS:
        resolved = IMAGE_MODELS[model]
        logger.debug(f"Resolved friendly name '{model}' to '{resolved}'")
        return resolved

    # If already has vendor/ prefix, pass through
    if "/" in model:
        logger.debug(f"Model '{model}' already has vendor prefix, passing through")
        return model

    # Otherwise, it's an error
    error_msg = (
        f"Unknown model '{model}'. Use a friendly name from IMAGE_MODELS "
        f"or a full litellm format like 'vendor/model-name'"
    )
    logger.error(error_msg)
    raise ValueError(error_msg)

