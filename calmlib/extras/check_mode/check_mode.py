from enum import Enum
from functools import wraps


def check_mode(allowed_modes=None, mode_attr="mode"):
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
