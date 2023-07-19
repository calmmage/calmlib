from . import utils
from .utils.code_keeper import remind, plant, garden_stats, code_keeper

try:
    from . import experimental
    from .experimental import config_mixin, gpt_router
except:
    pass

from .utils.lib_discoverer import LibDiscoverer

import importlib.metadata

try:
    __version__ = importlib.metadata.version('calmlib')
except:
    from loguru import logger

    logger.warning('failed to get version of calmlib, traceback:',
                   exc_info=True)
