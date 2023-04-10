import json
import os
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from itertools import zip_longest
from pathlib import Path
from typing import Dict
from typing import List, Union

import pyperclip
import logging
from .utils import cast_enum

logger = logging.getLogger(__file__)


# from aenum import MultiValueEnum


class GardenArea(Enum):
    main = 'main'
    secondary = 'secondary'
    inbox = 'inbox'


area_priority = {
    GardenArea.main: 1,
    GardenArea.secondary: 2,
    GardenArea.inbox: 3,
}


@dataclass
class CodeFragment:
    code: str
    tags: List[str]
    area: GardenArea
    metadata: Dict = None
    ext: str = '.py'

    @property
    def name(self):
        return '.'.join(self.tags)

    @property
    def path(self):
        return f"{self.area.value}/{self.name}{self.ext}"

    # name: str
    # categories: List[str]
    # id: str = None
    #
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        # if self.id is None:
        #     self.id = str(uuid.uuid4())
        #     # todo: _record_event - creation


DEFAULT_HOME_PATHS = ['~/home', '~/calmmage', '~']


# DEFAULT_GARDEN_ROOT = os.path.expanduser('~/code_garden')


class CodeGarden:
    def __init__(self, path=None):
        if path is None:
            path = self._find_garden()
        self.path = Path(path).expanduser()
        # create if not exists
        self.path.mkdir(parents=True, exist_ok=True)
        for area in GardenArea:
            (self.path / area.value).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _find_garden() -> str:
        # global DEFAULT_GARDEN_ROOT
        for home_path in DEFAULT_HOME_PATHS:
            DEFAULT_GARDEN_ROOT = (Path(home_path) / 'code_garden').expanduser()
            if DEFAULT_GARDEN_ROOT.exists():
                logger.info(
                    f"Found default code garden at {DEFAULT_GARDEN_ROOT}")
                break
        return os.getenv('CODE_GARDEN_ROOT', str(DEFAULT_GARDEN_ROOT))

    @staticmethod
    def _cast_area(area):
        return cast_enum(area, GardenArea)

    # -----------------
    # find
    # -----------------
    METADATA_KEY = "# metadata"

    def find(self,
             keys, area: Union[str, GardenArea] = None,
             keys_and: bool = True
             ) -> Dict[str, CodeFragment]:
        if isinstance(area, str):
            area = self._cast_area(area)
        areas = [area] if area is not None else GardenArea
        result = {}
        for area in areas:
            for path in self._find_paths(keys, area, keys_and):
                code = path.read_text()
                tags = path.stem.split('.')
                metadata = {}
                if code.startswith(f"{self.METADATA_KEY}"):
                    metadata_text, code = code.split('\n', 1)
                    metadata = json.loads(
                        metadata_text[len(self.METADATA_KEY):])
                code_fragment = CodeFragment(code, tags, area, metadata)
                result[code_fragment.path] = code_fragment
        return result

    def _find_paths(self, keys, area: GardenArea, keys_and: bool = True):
        area_path = self.path / area.value

        for path in area_path.iterdir():
            # just take .py files
            if path.suffix == '.py' and path.is_file():
                if keys_and and all(key in path.stem for key in keys):
                    yield path
                elif (not keys_and) and any(key in path.stem for key in keys):
                    yield path

    # -----------------
    # save
    # -----------------

    def save(self, code, tags, area: Union[str, GardenArea], metadata=None,
             force=False):
        area = self._cast_area(area)
        path = self._generate_path(area, tags)
        if path.exists() and not force:
            # check if code is already saved
            raise ValueError(f'Code already exists at {path}')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w') as f:
            if metadata is not None:
                f.write('# metadata ')
                json.dump(metadata, f)
                f.write('\n')
            f.write(code)

    def _generate_path(self, area: GardenArea, tags, ext='.py'):
        if not ext.startswith('.'):
            ext = '.' + ext
        area = self._cast_area(area)
        filename = '.'.join(tags) + ext
        return self.path / area.value / filename

    # -----------------
    # Summary
    # -----------------
    SWIMLINE = "~~~~~~~~~~~~~~~~~~\n"

    def generate_summary_by_tag(self, limit=None, swimlines=5):
        # count the number of code fragments per tag
        all_patterns = self.find("")
        counter = Counter()
        for pattern in all_patterns.values():
            counter.update(pattern.tags)

        items = counter.most_common(n=limit)
        # group by swimlines items
        tags_groups = zip_longest(*([iter(items)] * swimlines))

        result = ""
        for tags_chunk in tags_groups:
            for item in tags_chunk:
                if item is None:
                    break
                tag, count = item
                result += f"{tag}: {count}\n"
            result += self.SWIMLINE

        return result.strip()


class CodeKeeper:
    def __init__(self, code_garden: CodeGarden = None):
        if code_garden is None:
            code_garden = CodeGarden()  # finds path automatically
        elif isinstance(code_garden, str):
            code_garden = CodeGarden(code_garden)
        self.code_garden = code_garden

    # todo: read to_clipboard from config (env)
    def remind(self, keys: Union[str, List[str]] = None, area: Union[str,
    GardenArea] = None, keys_and: bool = True, to_clipboard=True) -> Dict[str,
    CodeFragment]:
        # step 1: parse the keys
        if keys is None:
            keys = ['remind']
        keys = self._parse_keys(keys)

        # step 2: find the code
        code_fragments = self.code_garden.find(keys, area, keys_and)

        # step 3: compose the formatted code
        res = ""
        for code_fragment in sorted(code_fragments.values(),
                                    key=lambda x: area_priority[x.area]):
            res += f"# {code_fragment.path}\n"
            res += f"{code_fragment.code}"
            res += f"\n\n"
        # todo: formatted code for jupyter

        # step 4: copy the code to the clipboard
        if to_clipboard:
            pyperclip.copy(res)

        return res

    @staticmethod
    def _parse_keys(keys):
        if isinstance(keys, str):
            keys = keys.split('.')
        return keys

    find = remind

    def plant(self, code: Union[str, Path], tags: Union[str, List[str]],
              area: Union[str, GardenArea] = GardenArea.inbox, force=False):
        # step 1: parse the tagline
        if isinstance(tags, str):
            if '/' in tags:
                area, tagline = tags.rsplit('/', 1)
            tags = self._parse_tagline(tags)

        # step 0: parse the code
        if Path(code).exists():
            code_path = Path(code)
            tags.append(code_path.stem)
            code = Path(code).read_text()

        # step 2: save the code
        self.code_garden.save(
            code, tags, area, force=force
        )

    @staticmethod
    def _parse_tagline(tagline):
        if isinstance(tagline, str):
            tagline = tagline.split('.')
        return tagline

    add = add_code = add_file = plant

    def generate_summary(self):
        summary = ""
        # genereate summary by tag (most used)
        summary += self.code_garden.generate_summary_by_tag()

        # todo: generate summary by usage (most visited / least visited)
        # todo: generate summary by creaetion date (most recent few)
        # todo: something else? How do I highlight the most important code?
        # random items just in case? :)
        return summary

    # todo: figure out intuitive name for this
    summary = generate_summary

    def help(self):
        print(self.generate_summary())
    # todo: SECTIONS TO ADD
    # SECTION 1: HOUSEKEEPING - sorting inbox etc.
    # SECTION 2: add Categories, Generate with AI, use for summary
    # SECTION 3: add logging, use for summary
    # SECTION 4: Notion, sync on startup, sync on save

    # def housekeeping(self):
    #     """Go over the garden and see about the plant names"""
    #     # 1) start with main first, then inbox, then secondary
    #     # 2) mark completed, completion time
    #     # 3) revisit
    #     # 4) revisit everything globally
    #     # 5) keep a global tag registry - with counts and introduction date / event dates.
    #     # 6) if there were many tag updates since the plant is finalised
    #     # 7) periodically run housekeeping. Send the requests for input through telegram


MemoryKeeper = CodeKeeper

if __name__ == '__main__':
    ck = CodeKeeper()
    print(ck.remind('remind'))
