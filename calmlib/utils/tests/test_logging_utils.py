from calmlib.utils.logging_utils import (
    is_logger_configured,
    configure_calmmage_logger,
)
from loguru import logger as loguru_logger


# Unit test for the logger configuration check
def test_logger_configuration():
    logger = loguru_logger
    # Ensures the check correctly identifies if the logger is already configured
    assert not is_logger_configured(
        logger
    ), "Logger should not be configured initially."
    configure_calmmage_logger(logger)
    assert is_logger_configured(
        logger
    ), "Logger should be configured after calling configure_calmmage_logger."
