import shutil
from pathlib import Path
from typing import Union


def trim(s, l=None, r=None):
    """
    Remove specified prefix or suffix from a string
    if it matches the start or end of the string exactly
    >>> trim("prefix_hello_suffix", l="prefix_", r="_suffix")
    'hello'
    >>> trim("prefix_hello_suffix", l="prefix_")
    'hello_suffix'
    >>> trim("prefix_hello_suffix", r="_suffix")
    'prefix_hello'
    >>> trim("prefix_hello_suffix", l="fix", r="fix")
    'prefix_hello_suf'
    """
    if l and s.startswith(l):
        s = s[len(l) :]
    if r and s.endswith(r):
        s = s[: -len(r)]
    return s


def rtrim(s, r):
    """
    Remove trailing suffix from a string if it matches the end of the string
    >>> rtrim("prefix_hello_suffix", "_suffix")
    'prefix_hello'
    >>> rtrim("prefix_hello_suffix", "_hello")
    'prefix_hello_suffix'
    >>> rtrim("prefix_hello_suffix", "_suf")  # does nothing
    'prefix_hello_suffix'
    """
    return trim(s, r=r)


def ltrim(s, l):
    """
    Remove leading prefix from a string if it matches the start of the string
    """
    return trim(s, l=l)


def is_subsequence(sub: str, main: str):
    """
    Check if sub is a subsequence of main
    Each character in sub should appear in main in the same order

    >>> is_subsequence('abc', 'abcde')
    True
    >>> is_subsequence('ace', 'abcde')
    True
    >>> is_subsequence('test', 'best_test')
    True
    >>> is_subsequence('abc', 'cba')
    False
    """
    sub_index = 0
    main_index = 0
    while sub_index < len(sub) and main_index < len(main):
        if sub[sub_index] == main[main_index]:
            sub_index += 1
        main_index += 1
    return sub_index == len(sub)


# region Path utils
Pathlike = Union[str, Path]


def fix_path(path: Pathlike) -> Path:
    path = Path(path)
    return path.expanduser().absolute()


def copy_tree(source, destination, overwrite=True):
    """ """
    source_path = Path(source)
    destination_path = Path(destination)

    if not source_path.is_dir():
        raise ValueError(f"Source ({source}) is not a directory.")

    if not destination_path.exists():
        destination_path.mkdir(parents=True)

    for item in source_path.iterdir():
        if item.is_dir():
            copy_tree(item, destination_path / item.name)
        else:
            if overwrite:
                shutil.copy2(item, destination_path / item.name)
            else:
                # todo: just skip? or raize an error?
                #  Or resolve interactively?
                #  Merge?
                #  Mark for merge?
                #  save side-by-side?
                #  for text - one solution, for non-text - another solution?
                raise NotImplementedError("Non-overwrite mode is Not implemented yet")


# endregion Path utils

# region Enum utils
from enum import Enum
from typing import Type, Union


def cast_enum(value, desired_type: Type[Enum]) -> Enum:
    if isinstance(value, desired_type):
        return value
    elif isinstance(value, Enum):
        value = value.value

    return desired_type(value)


Enumlike = Union[Enum, str]


def compare_enums(enum1: Enumlike, enum2: Enumlike):
    if isinstance(enum1, Enum):
        enum1 = enum1.value
    if isinstance(enum2, Enum):
        enum2 = enum2.value

    return enum1 == enum2


# endregion Enum utils
