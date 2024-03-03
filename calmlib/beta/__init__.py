# calmlib/beta/__init__.py
import importlib
import logging
import os
import sys

# Initialize __all__ for wildcard imports
__all__ = []

# Directory of the current file
dir_path = os.path.dirname(os.path.realpath(__file__))

# List everything in the directory
for item in os.listdir(dir_path):
    module_name, ext = os.path.splitext(item)
    # Filter out non-Python files and __init__.py
    if ext == ".py" and module_name != "__init__":
        try:
            # Dynamically import the module
            imported_module = importlib.import_module(
                "." + module_name, package="calmlib.beta"
            )
            setattr(sys.modules[__name__], module_name, imported_module)
            __all__.append(module_name)
        except Exception as e:
            logging.warning(f"Warning: Failed to import {module_name}: {e}")
