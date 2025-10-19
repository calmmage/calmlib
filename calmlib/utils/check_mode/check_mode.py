import os
from enum import Enum
from functools import wraps


def check_mode(allowed_modes=None, mode_attr="mode"):
    """Decorator for enforcing mode restrictions on methods.

    If called without arguments, returns the current CHECK_MODE environment variable as boolean.
    If called with arguments, returns a decorator for method mode checking.
    """
    # If no arguments provided, check environment variable
    if allowed_modes is None and mode_attr == "mode":
        return os.environ.get("CHECK_MODE", "").lower() in ("true", "1", "yes")

    def wrapped(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if allowed_modes is not None:
                if not hasattr(self, mode_attr):
                    raise AttributeError(f"Object {self} has no attribute {mode_attr}")
                if not isinstance(getattr(self, mode_attr), Enum):
                    raise ValueError(f"Attribute {mode_attr} is not an Enum")
                if getattr(self, mode_attr) not in allowed_modes:
                    raise ValueError(f"Mode {getattr(self, mode_attr)} not allowed")
            return func(self, *args, **kwargs)

        return wrapper

    return wrapped
