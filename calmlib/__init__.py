from importlib.metadata import PackageNotFoundError

from . import utils, audio, llm, logging, translate, user_interactions, telegram
from .llm import query_llm_text, query_llm_structured
from .logging import setup_logger, LogMode, LogFormat
from .utils import (
    fix_path,
    Pathlike,
    Enumlike,
    cast_enum,
    compare_enums,
    trim,
    find_env_key,
)
from .user_interactions import (
    ask_user,
    ask_user_choice,
    ask_user_confirmation,
    ask_user_raw,
    set_engine,
    get_engine,
)
from .telegram import BotKeyStore, BotKey

try:
    import importlib.metadata

    __version__ = importlib.metadata.version(__package__ or __name__)
    del importlib
except PackageNotFoundError:
    import toml
    from pathlib import Path

    path = Path(__file__).parent.parent / "pyproject.toml"
    __version__ = toml.load(path)["tool"]["poetry"]["version"]
    del toml, Path, path

__all__ = [
    "utils",
    "audio",
    "llm",
    "logging",
    "translate",
    "user_interactions",
    "telegram",
    "__version__",
    # llm
    "query_llm_text",
    "query_llm_structured",
    # logging
    "setup_logger",
    "LogMode",
    "LogFormat",
    # utils
    "fix_path",
    "Pathlike",
    "Enumlike",
    "cast_enum",
    "compare_enums",
    "trim",
    "find_env_key",
    # user_interactions
    "ask_user",
    "ask_user_choice",
    "ask_user_confirmation",
    "ask_user_raw",
    "set_engine",
    "get_engine",
    # telegram
    "BotKeyStore",
    "BotKey",
]