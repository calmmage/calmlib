from enum import Enum
import sys
from typing import Union, Optional
from loguru import logger as loguru_logger
from pathlib import Path


class LogFormat(str, Enum):
    DEFAULT = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
    ALTERNATIVE = "<level>{time:HH:mm:ss}</level> | <level>{message}</level>"
    DETAILED = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> | {message}"
    BRACKETED = "[<green>{time:HH:mm}</green>] [<level>{level}</level>] {message}"


class LogMode(str, Enum):
    DEV = "dev"  # Console + detailed output
    PROD = "prod"  # File-based, minimal console
    JUPYTER = "jupyter"  # Optimized for Jupyter cell output
    CUSTOM = "custom"  # Fully manual configuration


def setup_logger(
    logger=loguru_logger,
    level: str = "INFO",
    mode: LogMode = LogMode.CUSTOM,
    format: Union[LogFormat, str] = LogFormat.DEFAULT,
    console: bool = True,
    file: Optional[Union[str, Path]] = None,
    jupyter: bool = False,
    rotation: Optional[str] = None,  # e.g., "1 MB" or "00:00" for daily
    retention: Optional[str] = None,  # e.g., "7 days"
    colorize: bool = True,
):
    """
    Configure the loguru logger with flexible output options.

    Args:
        logger: The loguru logger instance to configure.
        level: Logging level (e.g., "INFO", "DEBUG").
        format: Log format (from LogFormat enum or custom string).
        mode: Predefined mode ("dev", "prod", "jupyter", "custom").
        console: Enable console output (sys.stderr by default).
        file: Path to log file (None disables file logging).
        jupyter: Enable Jupyter-specific output (sys.stdout).
        rotation: File rotation policy (e.g., "1 MB", "daily").
        retention: File retention policy (e.g., "7 days").
        colorize: Enable colorized output where supported.
    """
    logger.remove()  # Clear existing handlers

    # Adjust defaults based on mode
    if mode == LogMode.DEV:
        console = True
        jupyter = False
        file = None
        format = LogFormat.DETAILED
    elif mode == LogMode.PROD:
        console = True
        jupyter = False
        file = file or "app.log"
        format = LogFormat.DEFAULT
        rotation = rotation or "1 MB"
        retention = retention or "7 days"
    elif mode == LogMode.JUPYTER:
        console = False
        jupyter = True
        file = None
        format = LogFormat.DEFAULT

    # Add console sink (sys.stderr)
    if console:
        logger.add(
            sink=sys.stderr,
            format=format,
            level=level,
            colorize=colorize,
        )

    # Add Jupyter sink (sys.stdout)
    if jupyter:
        logger.add(
            sink=sys.stdout,
            format=format,
            level=level,
            colorize=colorize,
        )

    # Add file sink
    if file:
        logger.add(
            sink=Path(file),
            format=format,
            level=level,
            colorize=False,  # Files don’t need color
            rotation=rotation,
            retention=retention,
        )

    return logger


# Example usage
if __name__ == "__main__":
    logger = loguru_logger
    # Default dev mode
    setup_logger()
    logger.info("Dev mode: console only, detailed format")

    # Jupyter mode
    setup_logger(mode=LogMode.JUPYTER)
    logger.info("Jupyter mode: cell output")

    # Prod mode with custom file
    setup_logger(mode=LogMode.PROD, file="bot_logs.log")
    logger.info("Prod mode: console + file")

    # Custom configuration
    setup_logger(
        mode=LogMode.CUSTOM,
        console=True,
        jupyter=True,
        file="custom_logs.log",
        level="DEBUG",
        format=LogFormat.BRACKETED,
        rotation="500 KB",
    )
    logger.debug("Custom mode: all outputs enabled")
