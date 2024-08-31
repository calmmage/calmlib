import importlib
from loguru import logger
import sys
from pathlib import Path

# Initialize __all__ for wildcard imports
__all__ = []

# Directory of the current file
dir_path = Path(__file__).resolve().parent


# List everything in the directory
for item in dir_path.iterdir():
    if (item.suffix == ".py" and item.stem != "__init__") or item.is_dir():
        try:
            # Dynamically import the module
            imported_module = importlib.import_module("." + item.stem, package="calmlib.projects")
            setattr(sys.modules[__name__], item.stem, imported_module)
            __all__.append(item.stem)
        except Exception as e:
            logger.warning(f"Warning: Failed to import {item.stem}: {e}")
