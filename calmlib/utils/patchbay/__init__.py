"""Back-compat shim.

Implementation moved to the standalone package:

    ~/work/projects/patchbay  (import name: ``patchbay``)

This module re-exports the public API and aliases
``calmlib.utils.patchbay.*`` submodules onto ``patchbay.*`` so existing
imports keep working.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys

_PREFIX = "calmlib.utils.patchbay"
_TARGET = "patchbay"


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, target_name: str) -> None:
        self.target_name = target_name

    def create_module(self, spec):  # noqa: ANN001
        return importlib.import_module(self.target_name)

    def exec_module(self, module) -> None:  # noqa: ANN001
        return None


class _PatchbayAliasFinder(importlib.abc.MetaPathFinder):
    """Map calmlib.utils.patchbay.X → patchbay.X for submodule imports."""

    def find_spec(self, fullname, path, target=None):  # noqa: ANN001
        if fullname != _PREFIX and not fullname.startswith(_PREFIX + "."):
            return None
        # Root package is this file — only alias submodules.
        if fullname == _PREFIX:
            return None
        target_name = _TARGET + fullname[len(_PREFIX) :]
        try:
            target_spec = importlib.util.find_spec(target_name)
        except (ImportError, ModuleNotFoundError, ValueError):
            return None
        if target_spec is None:
            return None
        is_pkg = target_spec.submodule_search_locations is not None
        return importlib.util.spec_from_loader(
            fullname,
            _AliasLoader(target_name),
            is_package=is_pkg,
        )


def _install_finder() -> None:
    if any(isinstance(f, _PatchbayAliasFinder) for f in sys.meta_path):
        return
    sys.meta_path.insert(0, _PatchbayAliasFinder())


_install_finder()

# Public API re-export
from patchbay import *  # noqa: E402, F403
from patchbay import __all__ as __all__  # noqa: E402
