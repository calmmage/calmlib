from datetime import datetime
from pathlib import Path

# noinspection PyUnresolvedReferences
import pytest

from calmlib.tools.dev_env_setup.dev_env import CalmmageDevEnv


# todo
def test_start_new_project(tmp_path):
    """
    Test that the create_root method correctly creates the root directory and its subdirectories.
    """
    # Create CalmmageEnv class object at the temp path
    dev_env = CalmmageDevEnv(tmp_path)

    dev_env.start_new_project('test_project', local=True,
                              template_name='python_project')
    # # Run the create_root method
    # dev_env._setup_root_dir()
    #
    # # Validate the created folders
    #
    # expected_folders = latest_preset.dirs  # replace with the actual folder
    # # names
    # for folder in expected_folders:
    #     assert (tmp_path / folder).exists(), f"{folder} was not created"


# If you want to use pytest clea
if __name__ == '__main__':
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    tmp_path = Path(f'./tmp/new_local_project_{timestamp}').absolute()
    print(tmp_path)
    test_start_new_project(tmp_path)
