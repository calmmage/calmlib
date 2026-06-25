"""
Core user interaction functions with pluggable backend engines
"""

from typing import Any

from .config import _config
from .engines import (
    BotspotEngine,
    PythonInputEngine,
    ServiceTelegramHttpEngine,
    TyperEngine,
    UserInteractionEngine,
)


def set_engine(engine_type: str, **params: Any) -> None:
    """
    Set the user interaction engine

    Args:
        engine_type: Type of engine ('input', 'typer', 'botspot', 'telegram_service')
        **params: Parameters to pass to the engine constructor
    """
    engine_map = {
        "input": PythonInputEngine,
        "python": PythonInputEngine,
        "typer": TyperEngine,
        "botspot": BotspotEngine,
        "telegram_service": ServiceTelegramHttpEngine,
    }

    if engine_type not in engine_map:
        raise ValueError(
            f"Unknown engine type: {engine_type}. Available: {list(engine_map.keys())}"
        )

    engine_class = engine_map[engine_type]
    engine = engine_class(**params)
    _config.set_engine(engine, **params)


def get_engine() -> UserInteractionEngine:
    """Get the current user interaction engine"""
    return _config.get_engine()


async def ask_user(question: str, timeout: float | None = None) -> str | None:
    """
    Ask user a text question and get string response

    Args:
        question: Question to ask the user
        timeout: Optional timeout in seconds

    Returns:
        User's text response or None if cancelled/timeout
    """
    engine = get_engine()
    return await engine.ask_user(question, timeout=timeout)


async def ask_user_choice(
    question: str, choices: list[str] | dict[str, str], timeout: float | None = None
) -> str | None:
    """
    Ask user to choose from a list of options

    Args:
        question: Question to ask the user
        choices: List of choice strings or Dict mapping keys to display text
        timeout: Optional timeout in seconds

    Returns:
        Selected choice value or None if cancelled/timeout
    """
    engine = get_engine()
    return await engine.ask_user_choice(question, choices, timeout=timeout)


async def ask_user_confirmation(
    question: str, timeout: float | None = None
) -> bool | None:
    """
    Ask user a yes/no confirmation question

    Args:
        question: Question to ask the user
        timeout: Optional timeout in seconds

    Returns:
        True for yes, False for no, None if cancelled/timeout
    """
    engine = get_engine()
    return await engine.ask_user_confirmation(question, timeout=timeout)


async def ask_user_raw(question: str, timeout: float | None = None) -> Any | None:
    """
    Ask user and return raw response object (engine-dependent)

    Args:
        question: Question to ask the user
        timeout: Optional timeout in seconds

    Returns:
        Raw response object (type depends on engine) or None if cancelled/timeout
    """
    engine = get_engine()
    return await engine.ask_user_raw(question, timeout=timeout)


async def notify_user(message: str):
    engine = get_engine()
    return await engine.notify_user(message)
