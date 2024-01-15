
from datetime import datetime
from pathlib import Path

# noinspection PyUnresolvedReferences
import pytest

from calmlib.tools.dev_env_setup.dev_env import CalmmageDevEnv
from calmlib.tools.dev_env_setup.presets import latest_preset

# todo
def test_new_github_project():
    """
    Test that the create_root method correctly creates the root directory and its subdirectories.
    """
    # Create CalmmageEnv class object at the temp path
    dev_env = CalmmageDevEnv(tmp_path)

    # Run the create_root method
    dev_env._setup_root_dir()

    # Validate the created folders

    # expected_folders = latest_preset.dirs  # replace with the actual folder
    # # names
    # for folder in expected_folders:
    #     assert (tmp_path / folder).exists(), f"{folder} was not created"

    # delete the repo

# If you want to use pytest clea
if __name__ == '__main__':
    
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    name = f'test_cli_repo_creation_{timestamp}'
    # template_name = 'FAIL'
    template_name = 'bot-template'
    # env.
    make_repo_from_template(c, name, template_name)
    
    # tmp_path = Path(f'./tmp/root_dir_{timestamp}').absolute()
    # print(tmp_path)
    # test_setup_root_dir(tmp_path)
