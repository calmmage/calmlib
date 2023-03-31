from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Type

from aenum import MultiValueEnum
from dotenv import load_dotenv
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import PythonLexer

load_dotenv()


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
    def __init__(self, root=code_garden_root):
        self.root = root

    def plant(self, area, name, text):
        """plant the text in the area and give it the name"""
        area_path = Path(self.root, area.value)
        area_path.mkdir(parents=True, exist_ok=True)
        file_path = area_path / name
        with file_path.open("w") as f:
            f.write(text)

    add = plant

    def find(self, key):
        """Find all the plants related to key"""
        # simple for now: if the name contains the key
        result = []
        for area in FOLDERS:
            area_path = Path(self.root, area)
            for file_path in area_path.glob(f"*{key}*.py"):
                result.append((area, file_path))
        return result


class CodeKeeper:
    class CodeKeeper:
        def __init__(self, code_garden: CodeGarden = None):
            if code_garden is None:
                code_garden = self.find_the_garden()
            self.garden = code_garden
            pass

        @staticmethod
        def find_the_garden():
            """Find the code garden in the system
            - If path is specified - use it
            - If not specified - use the default one
            - If not found - create a new one
            """
            raise NotImplementedError()
            # return CodeGarden()

        def remind(self, key=None):
            if key is None:
                # Tell about all the topics in the garden
                topics = []
                for folder in FOLDERS:
                    area = GardenArea(folder)
                    area_path = Path(self.garden.root, area.value)
                    topics.extend([(area, p) for p in area_path.glob("*.py")])
                return topics
            else:
                # tell about the specific topic
                return self.garden.find(key)

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

        def _plant(self, code, area: GardenArea, tags: List[str],
                   desc: str = ""):
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

    # ---------------------------------------------------

    def find_code(self, key, to_clipboard=False, use_highlighting=False):
        found_files = self.remind(key)
        result = []
        for area, file_path in found_files:
            with file_path.open("r") as f:
                content = f.read()
                if use_highlighting:
                    content = highlight(content, PythonLexer(),
                                        TerminalFormatter())
                result.append((file_path.name, datetime.fromtimestamp(
                    file_path.stat().st_mtime), content))
            if to_clipboard:
                pyperclip.copy(content)
        return result

    def _find_area(area):
        return parse_enum(area, GardenArea)


# Additional functionality
def get_tags_from_filename(filename):
    return filename[:-3].split("_")


def rename_file_with_tags(file_path, new_tags):
    new_filename = "_".join(new_tags) + ".py"
    new_path = file_path.parent / new_filename
    file_path.rename(new_path)
