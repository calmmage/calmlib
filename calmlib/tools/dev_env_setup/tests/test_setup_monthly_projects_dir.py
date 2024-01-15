
from datetime import datetime
from pathlib import Path

# noinspection PyUnresolvedReferences
import pytest

from calmlib.tools.dev_env_setup.dev_env import CalmmageDevEnv


def test_setup_monthly_projects_dir(tmp_path):
    """
    Test that the create_root method correctly creates the root directory and its subdirectories.
    """
    # Create CalmmageEnv class object at the temp path
    dev_env = CalmmageDevEnv(tmp_path, setup=False)

    # Run the create_root method
    dev_env._setup_monthly_projects_dir(tmp_path)

    # Validate the created folders
    date = datetime.now()
    folder_name = date.strftime('%Y_%m_%b').lower()
    expected_folders = [
        folder_name,
        folder_name + '/experiments',
        folder_name + '/past_refs'
    ]
    # latest_preset.dirs)  # replace with the actual folder
    # # names
    for folder in expected_folders:
        assert (tmp_path / folder).exists(), f"{folder} was not created"


# If you want to use pytest clea
if __name__ == '__main__':
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    tmp_path = Path(f'./tmp/monthly_dir_{timestamp}').absolute()
    print(tmp_path)
    test_setup_monthly_projects_dir(tmp_path)
