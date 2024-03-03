# import os
# os.putenv("MAGIC_ENABLED", "1")
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/.env'))

try:
    from bmmb.logging_utils import get_logger

    logger = get_logger(to_mongo=False)
except:
    logger = logging.getLogger(__name__)


def get_calmlib_root():
    from pathlib import Path
    # if this file is in calmlib: use that
    if 'calmlib' in __file__:
        # get the path up to the first calmlib
        return __file__.rsplit('calmlib', 1)[0]
    # else check ./calmlib_path.txt
    else:
        config_path = Path(__file__).parent / 'calmlib_root.txt'
        calmlib_path = config_path.read_text().strip()
        return calmlib_path


calmlib_root = str(get_calmlib_root())
import sys

if calmlib_root not in sys.path:
    sys.path.append(calmlib_root)

# --------------------------------
# 1 init and run LibDiscoverer
# --------------------------------
try:
    from calmlib.utils.lib_discoverer import LibDiscoverer

    lib_discoverer = LibDiscoverer()

    # todo 2: add all the libs
    lib_discoverer.enable('code_keeper', depth=5)
    # 2.1 code keeper, memory keeper
    libs = [
        'calmlib',
        'gpt_kit',
        'bmmb'
    ]
    lib_discoverer.enable_libs(libs)
except:
    logger.warning('import lib_discoverer failed, traceback:', exc_info=True)

# todo 3: import all the libs. initialize default variables
# --------------------------------
# 3.1 defaultenv
# --------------------------------
try:
    from pathlib import Path
    import sys

    p = Path('~/home/lib/defaultenv').expanduser()
    sys.path.append(str(p))
    from defaultenv import ENVCD as env
except:
    logger.warning('import defaultenv failed, traceback:', exc_info=True)

# --------------------------------
# 3.2 code keeper
# --------------------------------
try:
    from calmlib.utils.code_keeper import remind, plant, garden_stats, \
        code_keeper

    remind()  # == remind('code_keeper')
except:
    logger.warning('import code_keeper failed, traceback:', exc_info=True)

# --------------------------------
# 3.3 gpt_kit
# --------------------------------
try:
    from gpt_kit import gpt_api, complete, complete_chat, edit, insert
    from gpt_kit.api.utils import init_gpt_api_key

    init_gpt_api_key()
    # todo: chat
    # usage: remind('gpt_kit')
except:
    logger.warning('import gpt_kit failed, traceback:', exc_info=True)

# --------------------------------
# 3.4 bmmb - app template
# --------------------------------
# todo

# --------------------------------
# 3.5 logging - bmmb.logging_utils
# --------------------------------
# todo

# --------------------------------
# 3.6 database - bmmb.data
# --------------------------------

try:
    from bmmb.data.mongo_utils import MongoItem, MongoTable, connect_mongo, \
        get_conn_str, MongoDatabase
    mongo_db_name = mongo_db_alias = 'jupyter'
    conn_str = get_conn_str()
    db = MongoDatabase(
        db_name=mongo_db_name, db_alias=mongo_db_alias, conn_str=conn_str
    )
    # for usage: remind("mongo.jupyter")
    logger = db.logger

    from mongoengine import \
        StringField as MongoString, \
        IntField as MongoInt, \
        FloatField as MongoFloat, \
        BooleanField as MongoBool, \
        DateTimeField as MongoDateTime, \
        ListField as MongoList, \
        DictField as MongoDict, \
        EmbeddedDocumentField as MongoEmbed, \
        ReferenceField as MongoReference
except:
    logger.warning('import mongoengine failed, traceback:', exc_info=True)


# 3.7 scheduler?
# 3.8 notion / bookmarks / archive

# 4. Basic libs, that I use all the time
try:
    import os, sys
    from tqdm.auto import tqdm
    from pathlib import Path
    from typing import Union, List, Dict, Any, Optional, Tuple, Callable, \
        TypeVar
    from pprint import pprint
    from functools import partial
    import time
    from datetime import datetime
    from copy import deepcopy
    from dataclasses import dataclass
    from enum import Enum
    from collections import defaultdict, Counter
    import json, pickle, toml, dotenv, yaml, pyperclip  # , requests, bs4, lxml
except:
    logger.warning('import libs failed, traceback:', exc_info=True)

if __name__ == '__main__':
    # todo: print info from memory keeper
    # option 1: remind about more stuff - like tqdm. remind('tqdm')
    # option 2: print the memory keeper info garden_stats()
    # option 3: print direcly some of the usages for the libs.
    pass

# prevent import optimisation
_ = remind, plant, garden_stats, code_keeper, \
    os, sys, tqdm, Path, Union, List, Dict, Any, Optional, Tuple, Callable, \
    TypeVar, pprint, partial, time, datetime, deepcopy, dataclass, Enum, \
    defaultdict, Counter
_ = json, pickle, toml, dotenv, yaml, pyperclip  # , requests, bs4, lxml
del libs, p
