from enum import Enum
from typing import Union

import sys
import loguru

class LogFormat(str, Enum):
    DEFAULT = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
    ALTERNATIVE = "<level>{time:HH:mm:ss}</level> | <level>{message}</level>"
    DETAILED = "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> | {message}"
    BRACKETED = "[<green>{time:HH:mm}</green>] [<level>{level}</level>] {message}"

def setup_logger(
    logger= loguru.logger,
    level: str = "INFO",
    format: Union[LogFormat, str] = LogFormat.DEFAULT
):
    logger.remove()  # Remove default handler

    logger.add(
        sink=sys.stderr,
        format=format,  # No need to access .value when inheriting from str
        colorize=True,
        level=level,
    )



if __name__ == "__main__":
    logger = loguru.logger
    for format in LogFormat:
        setup_logger(logger, format=format)
        print("Style: ", format)

        logger.debug("Hello, world!")
        logger.info("Hello, world!")
        logger.warning("Hello, world!")
        logger.error("Hello, world!")
        logger.critical("Hello, world!")

