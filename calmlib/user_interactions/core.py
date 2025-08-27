"""
Core user interaction functions with pluggable backend engines
"""
from typing import Any, Dict, List, Optional, Union

from .config import _config
from .engines import (
    UserInteractionEngine,
    PythonInputEngine, 
    TyperEngine,
    BotspotEngine,
    ServiceTelegramBotEngine,
)


def set_engine(engine_type: str, **params) -> None:
    """
    Set the user interaction engine
    
    Args:
        engine_type: Type of engine ('input', 'typer', 'botspot', 'telegram_service')
        **params: Parameters to pass to the engine constructor
    """
    engine_map = {
        'input': PythonInputEngine,
        'python': PythonInputEngine, 
        'typer': TyperEngine,
        'botspot': BotspotEngine,
        'telegram_service': ServiceTelegramBotEngine,
    }
    
    if engine_type not in engine_map:
        raise ValueError(f"Unknown engine type: {engine_type}. Available: {list(engine_map.keys())}")
    
    engine_class = engine_map[engine_type]
    engine = engine_class(**params)
    _config.set_engine(engine, **params)


def get_engine() -> UserInteractionEngine:
    """Get the current user interaction engine"""
    return _config.get_engine()


def ask_user(question: str, **kwargs) -> Optional[str]:
    """
    Ask user a text question and get string response
    
    Args:
        question: Question to ask the user
        **kwargs: Additional parameters passed to the engine
        
    Returns:
        User's text response or None if cancelled/timeout
    """
    engine = get_engine()
    return engine.ask_user(question, **kwargs)


def ask_user_choice(question: str, choices: Union[List[str], Dict[str, str]], **kwargs) -> Optional[str]:
    """
    Ask user to choose from a list of options
    
    Args:
        question: Question to ask the user
        choices: List of choice strings or Dict mapping keys to display text
        **kwargs: Additional parameters passed to the engine
        
    Returns:
        Selected choice value or None if cancelled/timeout
    """
    engine = get_engine()
    return engine.ask_user_choice(question, choices, **kwargs)


def ask_user_confirmation(question: str, **kwargs) -> Optional[bool]:
    """
    Ask user a yes/no confirmation question
    
    Args:
        question: Question to ask the user  
        **kwargs: Additional parameters passed to the engine
        
    Returns:
        True for yes, False for no, None if cancelled/timeout
    """
    engine = get_engine()
    return engine.ask_user_confirmation(question, **kwargs)


def ask_user_raw(question: str, **kwargs) -> Optional[Any]:
    """
    Ask user and return raw response object (engine-dependent)
    
    Args:
        question: Question to ask the user
        **kwargs: Additional parameters passed to the engine
        
    Returns:
        Raw response object (type depends on engine) or None if cancelled/timeout
    """
    engine = get_engine()
    return engine.ask_user_raw(question, **kwargs)