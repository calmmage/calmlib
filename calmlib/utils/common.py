from pathlib import Path
import shutil


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
