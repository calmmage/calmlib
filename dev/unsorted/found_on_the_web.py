import contextlib
import time

from calmlib import get_personal_logger

logger = get_personal_logger(__name__)


@contextlib.contextmanager
def stopwatch(message):
    """Context manager to print how long a block of code took."""
    t0 = time.time()
    try:
        yield
    finally:
        t1 = time.time()
        logger.debug('Total elapsed time for %s: %.3f' % (message, t1 - t0))
