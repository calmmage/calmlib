import logging
import math
import os
import sys
import time
from pathlib import Path

try:
    import numpy as np
    import pandas as pd
    from pandas import Timestamp, Timedelta
    import seaborn as sns
except:
    logging.warning("Failed to import numpy/pandas/seaborn, please pip install calmlib[full] for extra dependencies")


# dir_root = location of this file / .. / ..
def get_git_root():
    return Path(__file__).resolve().parent.parent.parent


git_root = get_git_root()

sys.path.append(os.path.expanduser(git_root / 'calmlib'))
sys.path.append(os.path.expanduser(git_root / 'simple-proto-db'))
sys.path.append(os.path.expanduser(git_root / 'simple-task-repeater'))

# todo: time
#  1) parse date
#  2) create timedelta
#  3) now - date, datetime
#  4) formatting - date, date with time

# todo: help - easily remembered method to remind everything else. Do modules have docstrings? Oh its not a module

# calmlib
import calmlib
from calmlib import autocast_args
from calmlib import load, load_json, load_pickle, dump, dump_json, dump_pickle
from calmlib import run_bg, run_cmd
from calmlib import get_personal_logger

# Make jupyter notebook display all output
from IPython.core.interactiveshell import InteractiveShell

InteractiveShell.ast_node_interactivity = "all"

__all__ = [np, pd, sns, time, sys, os, math, Path, Timestamp, Timedelta, autocast_args, load, load_pickle, load_json,
           dump_pickle, dump_json, dump, run_cmd, run_bg, get_personal_logger, calmlib, get_git_root]
