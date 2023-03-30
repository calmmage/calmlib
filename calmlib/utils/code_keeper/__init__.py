from enum import Enum
from typing import List, Type

from aenum import MultiValueEnum


class GardenArea(MultiValueEnum):
    inbox = 'inbox'
    secondary = 'secondary'
    main = 'main'


# todo: move to utils
def parse_enum(value, desired_type: Type[Enum]) -> Enum:
    if isinstance(value, desired_type):
        return value
    elif isinstance(value, Enum):
        value = value.value

    return desired_type(value)


class Singleton:
    pass


# todo: find and import singleton mixin class in some public library
class CodeGarden(Singleton):
    def __init__(self, root):
        self.root = root

    def plant(self, area, name, text):
        """plant the text in the area and give it the name"""

    add = plant

    def find(self, key):
        """Find all the plants related to key"""
        # simple for now: if the name contains the key
        # todo: implement


class CodeKeeper:
    def __init__(self, code_garden: CodeGarden = None):
        if code_garden is None:
            code_garden = self.find_the_garden()
        self.garden = code_garden
        pass

    @staticmethod
    def find_the_garden():
        raise NotImplementedError()

    def remind(self, key=None):
        if key is None:
            raise NotImplementedError()
        # tell about all the topics in the garden
        else:
            raise NotImplementedError()

    # find all the snippets related / tagged with this
    # or tell about the area
    # todo: sort. Sort, using gpt?

    find = remind

    def __getitem__(self, key):
        return self.find(key)

    def plant(self, snippet, area=None, tags=None, desc=""):
        """
        snippet: snippet in the free format
        """
        # todo: use gpt to enrich / extract the missing data - from snippet
        self._plant(snippet, area, tags, desc)

    add = plant

    @staticmethod
    def _find_area(area):
        return parse_enum(area, GardenArea)

    def _plant(self, code, area: GardenArea, tags: List[str], desc: str = ""):
        """
        code: code to be saved
        area: area (dir) in the garden
        tags:
        """
        text = desc + code
        name = "_".join(tags) + '.py'

        self.garden.plant(area, name, text)

    _add = _plant

    def housekeeping(self):
        """Go over the garden and see about the plant names"""
        # 1) start with main first, then inbox, then secondary
        # 2) mark completed, completion time
        # 3) revisit
        # 4) revisit everything globally
        # 5) keep a global tag registry - with counts and introduction date / event dates.
        # 6) if there were many tag updates since the plant is finalised
        # 7) periodically run housekeeping. Send the requests for input through telegram
        pass
