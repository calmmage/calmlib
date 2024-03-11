from enum import Enum
from typing import Type


# tagline = "sample_tag_set.test.garden"
# expected output: ['sample', 'tag','set','test','garden']

# chars = '.'  # '._'
# split_pattern = re.compile(f"[{chars}]")
#
#
# def parse_tagline(tagline) -> Set[str]:
#     """Parse a tagline into a set of tags
#     uses chars = '._' as separators
#     """
#     return set(split_pattern.split(tagline))

# todo: move to calmlib utils - can be used in multiple places.
def cast_enum(value, desired_type: Type[Enum]) -> Enum:
    if isinstance(value, desired_type):
        return value
    elif isinstance(value, Enum):
        value = value.value

    return desired_type(value)
