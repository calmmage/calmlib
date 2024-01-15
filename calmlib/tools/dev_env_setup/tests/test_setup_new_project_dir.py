from datetime import datetime
from pathlib import Path

# noinspection PyUnresolvedReferences
import pytest

from calmlib.tools.dev_env_setup.dev_env import CalmmageDevEnv


def test_setup_new_project_dir(tmp_path, project_name=None):
    """
    Test that the create_root method correctly creates the root directory and its subdirectories.
    """
    # Create CalmmageEnv class object at the temp path
    dev_env = CalmmageDevEnv(tmp_path)

    # Run the create_root method
    dev_env._setup_new_project_dir('test_project', root=tmp_path)

    # Validate the created folders

    expected_folders = ['test_project']  # replace with the actual folder
    # names
    for folder in expected_folders:
        assert (tmp_path / folder).exists(), f"{folder} was not created"


# If you want to use pytest clea
if __name__ == '__main__':
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    tmp_path = Path(f'./tmp/project_dir_{timestamp}').absolute()
    print(tmp_path)
    test_setup_new_project_dir(tmp_path, 'test_project')
