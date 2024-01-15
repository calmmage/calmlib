from datetime import datetime
from pathlib import Path

# noinspection PyUnresolvedReferences
import pytest

from calmlib.tools.dev_env_setup.dev_env import CalmmageDevEnv
from calmlib.tools.dev_env_setup.presets import latest_preset


def test_monthly_job(tmp_path):
    """
    Test that the create_root method correctly creates the root directory and its subdirectories.
    """
    # Create CalmmageEnv class object at the temp path
    dev_env = CalmmageDevEnv(tmp_path, setup=False)
    dev_env._setup_root_dir()

    # Run the create_root method
    dev_env.monthly_job()

    # Validate the created folders
    expected_folders = [
        latest_preset.seasonal_projects_dir + '/latest',
        'playground'
    ]
    # names
    for folder in expected_folders:
        assert (tmp_path / folder).exists(), f"{folder} was not created"
    # check that soft links point to the right dirs
    # latest -> monthly dir
    date = datetime.now()
    folder_name = date.strftime('%Y_%m_%b').lower()
    source = tmp_path / latest_preset.seasonal_projects_dir / folder_name
    target = tmp_path / latest_preset.seasonal_projects_dir / 'latest'
    assert target.is_symlink()
    assert target.resolve() == source.resolve()

    # playground -> latest
    source = tmp_path / latest_preset.seasonal_projects_dir / 'latest' / 'experiments'
    target = tmp_path / 'playground'
    assert target.is_symlink()
    assert target.resolve() == source.resolve()


# If you want to use pytest clea
if __name__ == '__main__':
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    tmp_path = Path(f'./tmp/monthly_job_{timestamp}').absolute()
    print(tmp_path)
    test_monthly_job(tmp_path)
