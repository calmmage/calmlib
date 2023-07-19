from .core import CodeKeeper, GardenArea
from typing import List, Union

# todo: make code_keeper a singleton / factory?
code_keeper = CodeKeeper()


def remind(keys=None, area=None, keys_and=True, to_clipboard=True):
    """Remind me of code in my code garden."""
    res = code_keeper.remind(keys=keys, area=area, keys_and=keys_and,
                             to_clipboard=to_clipboard)
    print(res)


def plant(code, tags: Union[str, List[str]], area=GardenArea.inbox):
    """Plant code in my code garden.
    code: str or path

    tagline: str or list of str
    example: 'tag1.tag2.tag3'

    area: inbox, main or secondary
    also, can be specified in the tags: 'main/tag1.tag2.tag3'
    """
    return code_keeper.plant(code, tags=tags, area=area)


def garden_stats():
    """Get stats about my code garden."""
    res = code_keeper.generate_summary()
    print(res)
