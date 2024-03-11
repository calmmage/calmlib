from loguru import logger as loguru_logger
from pathlib import Path

# Default log directory and file
DEFAULT_LOG_DIR = Path("~/.calmmage/logs").expanduser()
DEFAULT_LOG_FILE = "calmlib.log"


def is_logger_configured(logger_instance, path=None):
    """
    Checks if the logger has at least one handler configured
    already has at least 2 handlers: sys and file
    """
    # todo: use 'path' to check if the logger is configured with the specified file
    return len(logger_instance._core.handlers) >= 2


def configure_calmmage_logger(logger_instance, path=None):
    if not path:
        path = DEFAULT_LOG_DIR / DEFAULT_LOG_FILE
    if is_logger_configured(logger_instance, path):
        logger_instance.warning("Logger already configured, skipping configuration")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    logger_instance.add(path, rotation="10 MB", enqueue=True)


def get_logger(name=None, level="INFO", format=None, log_file=None):
    # todo: get a logger with a specific name - use loguru.bind
    # todo: set logger level
    # todo: set logger format
    # todo: set logger path
    logger = loguru_logger
    if level != "INFO":
        logger.warning("Level is unused for now")
    if format:
        logger.warning("Format is unused for now")
    if log_file:
        logger.warning("Log file varaible is unused for now")
    if not is_logger_configured(logger):
        configure_calmmage_logger(logger)
    return logger
