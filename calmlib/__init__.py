from . import utils, beta

# try:
#     from . import experimental
#     from .experimental import config_mixin, gpt_router
# except:
#     pass

from calmlib.tools.lib_discoverer import LibDiscoverer

from importlib.metadata import PackageNotFoundError

try:
    import importlib.metadata

    __version__ = importlib.metadata.version(__package__ or __name__)
    del importlib
except PackageNotFoundError:
    import toml
    from pathlib import Path

    path = Path(__file__).parent.parent / "pyproject.toml"
    __version__ = toml.load(path)["tool"]["poetry"]["version"]
    del toml, Path, path
