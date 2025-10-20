import shutil
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Type, Union


def trim(string, left=None, right=None):
    """
    Remove specified prefix or suffix from a string
    if it matches the start or end of the string exactly
    >>> trim("prefix_hello_suffix", left="prefix_", right="_suffix")
    'hello'
    >>> trim("prefix_hello_suffix", left="prefix_")
    'hello_suffix'
    >>> trim("prefix_hello_suffix", right="_suffix")
    'prefix_hello'
    >>> trim("prefix_hello_suffix", left="fix", right="fix")
    'prefix_hello_suf'
    """
    if left and string.startswith(left):
        string = string[len(left) :]
    if right and string.endswith(right):
        string = string[: -len(right)]
    return string


def rtrim(string, right):
    """
    Remove trailing suffix from a string if it matches the end of the string
    >>> rtrim("prefix_hello_suffix", "_suffix")
    'prefix_hello'
    >>> rtrim("prefix_hello_suffix", "_hello")
    'prefix_hello_suffix'
    >>> rtrim("prefix_hello_suffix", "_suf")  # does nothing
    'prefix_hello_suffix'
    """
    return trim(string, right=right)


def ltrim(string, left):
    """
    Remove leading prefix from a string if it matches the start of the string
    """
    return trim(string, left=left)


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
class Singleton(type):
    """
    Singleton metaclass.
    Usage example:
    class MyClass(BaseClass, metaclass=Singleton):
        pass
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


def cleanup_none(data: Union[Dict, List[Dict]], none_entities=(None,), skip_keys=()):
    if isinstance(data, list):
        for item in data:
            cleanup_none(item, skip_keys=skip_keys)
    elif isinstance(data, dict):
        to_delete = set()
        for key, value in data.items():
            if key in skip_keys:
                continue
            if any([value is none for none in none_entities]):
                to_delete.add(key)
            elif isinstance(value, (dict, list)):
                cleanup_none(value, skip_keys=skip_keys)

        for key in to_delete:
            del data[key]
    return data


def dict_to_namespace(data):
    """Recursively convert dict to SimpleNamespace for dot access."""
    if isinstance(data, dict):
        return SimpleNamespace(**{k: dict_to_namespace(v) for k, v in data.items()})
    elif isinstance(data, list):
        return [dict_to_namespace(item) for item in data]
    else:
        return data


def sample_structure(data: Union[Dict, List]) -> Union[Dict, List]:
    """
    Recursively sample nested dict/list structure by reducing all lists to single first item.
    Preserves the nested structure while making it more compact for inspection.

    >>> sample_structure({'items': [{'id': 1}, {'id': 2}], 'name': 'test'})
    {'items': [{'id': 1}], 'name': 'test'}
    >>> sample_structure({'a': {'b': [1, 2, 3]}})
    {'a': {'b': [1]}}
    """
    if isinstance(data, dict):
        return {key: sample_structure(value) for key, value in data.items()}
    elif isinstance(data, list) and len(data) > 0:
        return [sample_structure(data[0])]
    elif isinstance(data, list):
        return []
    else:
        return data
