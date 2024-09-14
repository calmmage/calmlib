import json
import pickle
from pathlib import Path

from calmlib.autocast import autocast_args


@autocast_args()
def dump_json(obj, path):
    with open(path, 'w') as f:
        return json.dump(obj, f)


@autocast_args()
def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


@autocast_args()
def dump_pickle(obj, path):
    with open(path, 'wb') as f:
        return pickle.dump(obj, f)


@autocast_args()
def load_pickle(path):
    with open(path, 'rb') as f:
        return pickle.load(f)


serialization_handlers = {'json': 'json', 'pickle': 'pickle', 'pkl': 'pickle'}


@autocast_args()
def dump(obj, path: Path):
    path = Path(path)
    for handler_suffix, handler in serialization_handlers.items():
        if path.name.endswith(handler_suffix):
            handler_name = f'dump_{handler}'
            dump_handler = globals().get(handler_name)
            return dump_handler(obj, path)


@autocast_args()
def load(path: Path):
    path = Path(path)
    for handler_suffix, handler in serialization_handlers.items():
        if path.name.endswith(handler_suffix):
            handler_name = f'load_{handler}'
            load_handler = globals().get(handler_name)
            return load_handler(path)


def get_token(path):
    return Path(path).read_text().strip()
