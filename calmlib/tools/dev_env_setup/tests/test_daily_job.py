from datetime import datetime
from pathlib import Path

# noinspection PyUnresolvedReferences
import pytest

from calmlib.tools.dev_env_setup.dev_env import CalmmageDevEnv


def test_daily_job(tmp_path):
    """
    Test that the create_root method correctly creates the root directory and its subdirectories.
    """
    # Create CalmmageEnv class object at the temp path
    dev_env = CalmmageDevEnv(tmp_path, setup=True)

    # setup some folders ±like projects
    projects_dir = dev_env.seasonal_projects_dir / 'latest'
    project_dir = projects_dir / 'test_project'
    project_dir.mkdir(parents=True, exist_ok=True)

    # Run the create_root method
    dev_env.daily_job()

    target_dir = dev_env.project_unsorted_dir / 'test_project'
    assert target_dir.is_symlink()
    assert target_dir.resolve() == project_dir.resolve()


# If you want to use pytest clea
if __name__ == '__main__':
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    tmp_path = Path(f'./tmp/daily_job_{timestamp}').absolute()
    print(tmp_path)
    test_daily_job(tmp_path)
