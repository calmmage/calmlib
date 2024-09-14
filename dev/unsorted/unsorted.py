from pathlib import Path

from calmlib.autocast import autocast_args


@autocast_args
def fix_path(path: Path):
    return path.expanduser().absolute()


def trim(l: str, s="", e=""):
    if l.startswith(s):
        l = l[len(s) or None:]
    if l.endswith(e):
        l = l[:-len(e) or None]
    return l


def rtrim(l, e):
    return trim(l, e=e)
