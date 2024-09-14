from pathlib import Path


# import os


# add to ipython and jupyter
def add_to_ipython(source_path):
    # create softlink
    target_path = Path(
        '~').expanduser() / '.ipython/profile_default/startup/startup.py'

    if not target_path.exists():
        # create the target path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.symlink_to(source_path)

    # put calmlib root near the startup file
    from startup import calmlib_root
    calmlib_root_path = target_path.parent / 'calmlib_root.txt'
    calmlib_root_path.write_text(calmlib_root)


# add to bashrc
def add_to_bashrc(source_path):
    # create softlink
    command_to_add = f'\npython {source_path}\n'

    # if .zshrc exists, use that instead
    target_path = Path('~').expanduser() / '.zshrc'
    if not target_path.exists():
        target_path = Path('~').expanduser() / '.bashrc'

    text = target_path.read_text()
    if command_to_add in text:
        # already added
        # could be commented out - that would be on purpose
        return

    with open(target_path, 'a') as f:
        f.write(command_to_add)


# todo: add to pycharm

def main(path=None):
    if path is None:
        # assume that this file is in the same directory as the main.py file
        # path = os.path.dirname(os.path.abspath(__file__))
        path = Path(__file__).parent / 'startup.py'
    add_to_ipython(path)
    add_to_bashrc(path)


if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()

    parser.add_argument('--path', type=str, default=None)

    args = parser.parse_args()

    main(**vars(args))
