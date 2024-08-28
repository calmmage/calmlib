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
