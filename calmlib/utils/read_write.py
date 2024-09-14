import json
import pickle
from os import PathLike
from pathlib import Path

from calmlib.utils.main import Pathlike


def dump_json(obj, path: PathLike, indent=2, **kwargs):
    with open(path, "w") as f:
        return json.dump(obj, f, indent=indent)


def load_json(path: PathLike):
    with open(path, "r") as f:
        return json.load(f)


def dump_pickle(obj, path: PathLike):
    with open(path, "wb") as f:
        return pickle.dump(obj, f)


def load_pickle(path: PathLike):
    with open(path, "rb") as f:
        return pickle.load(f)


load_handlers = {".json": load_json, ".pickle": load_pickle, ".pkl": load_pickle}
dump_handlers = {".json": dump_json, ".pickle": dump_pickle, ".pkl": dump_pickle}


def dump(obj, path: Pathlike):
    path = Path(path)
    handler = dump_handlers.get(path.suffix)
    if handler:
        return handler(obj, path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")


def load(path: Pathlike):
    path = Path(path)
    handler = load_handlers.get(path.suffix)
    if handler:
        return handler(path)
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")


def get_token(path):
    return Path(path).read_text().strip()
