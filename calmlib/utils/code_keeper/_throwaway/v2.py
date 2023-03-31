import argparse
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import PythonLexer

load_dotenv()

# Loading variables from .env file
CODE_GARDEN_ROOT = os.getenv("CODE_GARDEN_ROOT",
                             os.path.expanduser("~/code_keeper"))
FOLDERS = os.getenv("FOLDERS", "inbox,main,secondary").split(',')

# Adding argparse support
parser = argparse.ArgumentParser(description="Code Garden arguments")
parser.add_argument("--root", default=CODE_GARDEN_ROOT,
                    help="Code garden root directory")
args = parser.parse_args()

if __name__ == "__main__":
    code_garden_root = args.root
else:
    code_garden_root = CODE_GARDEN_ROOT


class CodeGarden(Singleton):
    def __init__(self, root=code_garden_root):
        self.root = root

    def plant(self, area, name, text):
        area_path = Path(self.root, area.value)
        area_path.mkdir(parents=True, exist_ok=True)
        file_path = area_path / name
        with file_path.open("w") as f:
            f.write(text)

    def find(self, key):
        result = []
        for area in FOLDERS:
            area_path = Path(self.root, area)
            for file_path in area_path.glob(f"*{key}*.py"):
                result.append((area, file_path))
        return result


class CodeKeeper:
    @staticmethod
    def find_the_garden():
        return CodeGarden()

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
            return self.garden.find(key)

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
