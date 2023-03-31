from .core import CodeKeeper, GardenArea

# todo: make code_keeper a singleton / factory?
code_keeper = CodeKeeper()


def remind(keys=None, area=None, keys_and=True, to_clipboard=True):
    """Remind me of code in my code garden."""
    return code_keeper.remind(keys=keys, area=area, keys_and=keys_and,
                              to_clipboard=to_clipboard)


def plant(code, tags, area=GardenArea.inbox):
    """Plant code in my code garden.
    code: str or path

    tags: str or list of str
    example: 'tag1.tag2.tag3'

    area: inbox, main or secondary
    also, can be specified in the tags: 'main/tag1.tag2.tag3'
    """
    return code_keeper.plant(code, tags=tags, area=area)


def garden_stats():
    """Get stats about my code garden."""
    return code_keeper.generate_summary()
