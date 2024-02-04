import os
from datetime import datetime
from pathlib import Path
from shutil import copyfile

import git
from dotenv import load_dotenv

from calmlib.tools.dev_env_setup.presets import latest_preset

DEFAULT_ROOT_DIR = "~/work"
DEFAULT_APP_DATA_DIR = "~/.calmmage"


class CalmmageDevEnv:
    def __init__(
        self,
        root_dir=DEFAULT_ROOT_DIR,
        app_data_dir=DEFAULT_APP_DATA_DIR,
        preset=None,
        setup=False,
        overwrite=False,
    ):
        load_dotenv()  # load environment variables from .env file
        self.app_data_dir = Path(app_data_dir).expanduser()
        self.root_dir = Path(root_dir).expanduser()
        if preset is None:
            preset = latest_preset
        self.preset = preset

        if self.root_dir.exists() and list(self.root_dir.iterdir()) and not overwrite:
            if not self._validate_structure():
                raise ValueError(
                    f"root dir exists but has invalid structure: {self.root_dir}. Set overwrite=True to ignore that"
                )

        self._github_client = None
        # todo: accept logger as kwarg
        # todo: add calmlib.setup_logger to calmlib - find where I have it
        # todo: use calmlib.setup_logger
        self._logger = None
        self._templates = None
        self._local_templates = None

        if setup or overwrite:
            self.setup()

    def setup(self):
        self._setup_root_dir()
        self._setup_monthly_projects_dir()
        # self._setup_new_project_dir('test')
        self.monthly_job()
        # self.daily_job()

    def setup_shell_profiles(self):
        self._setup_app_data_dir()

    def _validate_structure(self):
        paths = self.preset.dirs
        for path in paths:
            if not (self.root_dir / path).exists():
                return False
        return True
        # raise ValueError(f"Missing directory: {path}")

    @property
    def logger(self):
        if self._logger is None:
            from loguru import logger

            self._logger = logger
        return self._logger

    @property
    def github_client(self):
        if self._github_client is None:
            from github import Github

            token = os.getenv("GITHUB_API_TOKEN")
            if token is None:
                raise ValueError("Missing GitHub API token")
            self._github_client = Github(token)
        return self._github_client

    @property
    def seasonal_projects_dir(self):
        return self.root_dir / self.preset.seasonal_projects_dir
        # return self.root_dir / 'code' / 'seasonal'

    @property
    def new_projects_dir(self):
        return self.root_dir / self.preset.new_projects_dir
        # return self.seasonal_projects_dir / 'latest' / 'experiments'

    @property
    def project_unsorted_dir(self):
        return self.root_dir / self.preset.project_unsorted_dir
        # return self.root_dir / 'code' / 'structured' / 'unsorted'

    def _setup_root_dir(self):
        root_dir = Path(self.root_dir).expanduser()
        root_dir.mkdir(parents=True, exist_ok=True)

        paths = self.preset.dirs
        # paths = [
        #     "code/seasonal/past",
        #     "code/structured/unsorted",
        #     "code/structured/libs",
        #     "code/structured/tools",
        #     "code/structured/projects",
        #     "code/structured/archive",
        #     "workspace/launchd/scripts"
        #     "workspace/launchd/logs"
        # ]
        for path in paths:
            (root_dir / path).mkdir(parents=True, exist_ok=True)

    def _setup_monthly_projects_dir(self, root=None, date=None):
        """
        seasonal
        """
        # "YYYY_MM_MMM".lower()
        if date is None:
            date = datetime.now()
        folder_name = date.strftime("%Y_%m_%b").lower()
        if root is None:
            root = self.seasonal_projects_dir
        else:
            root = Path(root)
        monthly_project_dir = root / folder_name
        if monthly_project_dir.exists():
            # already exists - nothing to do
            self.logger.warning(
                f"Monthly project dir already exists: {monthly_project_dir}"
            )
            return monthly_project_dir
        monthly_project_dir.mkdir(parents=True, exist_ok=True)
        paths = ["experiments", "past_refs"]
        for path in paths:
            (monthly_project_dir / path).mkdir(parents=True, exist_ok=True)
        return monthly_project_dir

    def _setup_new_project_dir(self, name, root=None):
        # code/seasonal
        if root is None:
            root = self.new_projects_dir
        else:
            root = Path(root)
        # folder = code/seasonal/latest/experiments
        project_dir = root / name
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    def monthly_job(self):
        # create seasonal folder
        projects_dir = self._setup_monthly_projects_dir()

        # link seasonal folder to the 'latest'
        source = projects_dir
        target = self.seasonal_projects_dir / "latest"
        # create softlink
        # Check if the symlink already exists
        if target.is_symlink():
            #  Delete and create new
            target.unlink()
        target.symlink_to(source)

        # link "playground" to the latest/experiments
        source = target / "experiments"
        target = self.root_dir / "playground"
        if target.is_symlink():
            #  Delete and create new
            target.unlink()
        target.symlink_to(source)

        # todo: something else?
        # todo: archive all the projects from the /unsorted folder?
        # only very old ones..

        # any ideas of what i want to do here? Think later, on a clear head
        # good as is for now

    def daily_job(self):
        # link all the new projects to the ... structured / unsorted
        projects_dir = self.seasonal_projects_dir / "latest"
        target_dir = self.project_unsorted_dir
        for project_dir in projects_dir.iterdir():
            # skip 'experiments' and 'past_ref' folders
            if project_dir.name in ["experiments", "past_refs"]:
                continue
            if project_dir.is_dir():
                target_path = target_dir / project_dir.name
                if not target_path.exists():
                    target_path.symlink_to(project_dir)

    def _create_github_project_from_template(self, name, template_name):
        # create project dir
        project_dir = self._setup_new_project_dir(name)

        # create repo
        self._create_repo_from_template(name, template_name)

        # git clone
        token = os.getenv("GITHUB_API_TOKEN")
        username = self.github_client.get_user().login
        url = f"https://{token}@github.com/{username}/{name}.git"

        # self.github_client.get_user().get_repo(name).clone(str(project_dir))
        target_dir = str(project_dir)
        git.Git(target_dir).clone(url)
        return project_dir

    def start_new_project(self, name, local=True, template_name=None):
        if local:
            return self._create_local_project_from_template(name, template_name)
        else:
            return self._create_github_project_from_template(name, template_name)

    def list_templates(self, local=True):
        if local:
            templates_dir = Path(__file__).parent / "resources" / "templates"
            return [
                template.name
                for template in templates_dir.iterdir()
                if template.is_dir()
            ]
        else:
            # github
            return self.get_github_template_names()

    # github
    def get_templates(self, reset_cache=False):
        if self._templates is None or reset_cache:
            repos = self.github_client.get_user().get_repos()
            self._templates = {repo.name: repo for repo in repos if repo.is_template}
        return self._templates

    def get_template(self, name, reset_cache=False):
        templates = self.get_templates(reset_cache=reset_cache)
        return templates[name]

    def get_github_template_names(self, reset_cache=False):
        templates = self.get_templates(reset_cache=reset_cache)
        return list(templates.keys())

    # def get_repos(self, reset_cache=False):

    def _create_repo_from_template(self, name, template_name):
        # create a new repo from template
        github_client = self.github_client

        # get the new repository
        # new_repo = github_client.get_user().get_repo(name)
        username = github_client.get_user().login
        template_owner = username
        # check template name is valid
        templates = self.get_github_template_names()
        if template_name not in templates:
            raise ValueError(
                f"Invalid template name: {template_name}. Available templates: {templates}"
            )

        # make the API call to create the repository from the template
        github_client._Github__requester.requestJsonAndCheck(
            "POST",
            f"/repos/{template_owner}/{template_name}/generate",
            input={"owner": username, "name": name},
        )

        # return the repo link ?
        return f"https://github.com/{username}/{name}"

    # local
    def get_local_template(self, name):
        templates = self.get_local_templates()
        return templates[name]

    def get_local_templates(self):
        if self._local_templates is None:
            templates_dir = Path(__file__).parent / "resources" / "templates"
            self._local_templates = {
                template.name: template
                for template in templates_dir.iterdir()
                if template.is_dir()
            }
        return self._local_templates

    def get_local_template_names(self):
        templates = self.get_local_templates()
        return list(templates.keys())

    def _create_local_project_from_template(self, name, template_name):
        project_dir = self._setup_new_project_dir(name)

        # use local templates
        script_dir = Path(__file__).parent
        templates_dir = script_dir / "resources" / "templates"

        templates = self.get_local_template_names()
        if template_name not in templates:
            raise ValueError(
                f"Invalid template name: {template_name}. Available templates: {templates}"
            )
        # copy template to the new project dir
        template_dir = self.get_local_template(template_name)
        from distutils.dir_util import copy_tree

        copy_tree(str(template_dir), str(project_dir))

        return project_dir

    # --------------------------------------------
    # Aliases
    # --------------------------------------------

    def _copy_resource(self, resource_name):
        source_path = Path(__file__).parent / "resources" / resource_name
        target_path = self.app_data_dir / resource_name
        copyfile(source_path, target_path)

    def _copy_aliases(self):
        self._copy_resource(".alias")

    profile_files = ["~/.bash_profile", "~/.bashrc", "~/.zshrc"]

    def _source_line(self, line, targets=None):
        if targets is None:
            targets = self.profile_files
        for profile in targets:
            profile = Path(profile).expanduser()
            if profile.exists():
                if line not in profile.read_text():
                    with open(profile, "a") as f:
                        f.write(line)
                        f.write("\n")

    def _source_aliases(self):
        line = f"source {self.app_data_dir}/.alias"
        self._source_line(line)

    # --------------------------------------------
    # bashrc
    # --------------------------------------------
    # setup bashrc
    def _copy_shrc(self):
        self._copy_resource(".zshrc")

    def _source_shrc(self):
        line = f"source {self.app_data_dir}/.zshrc"
        self._source_line(line)
        # self._source_file(self.app_data_dir / '.zshrc')

    # --------------------------------------------
    # startup.py
    # --------------------------------------------

    def _setup_app_data_dir(self):
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self._copy_aliases()
        self._copy_shrc()
        self._source_aliases()
        self._source_shrc()
        self._custom_1()
        self._custom_2()
        self._custom_3()
        self._custom_4()

    def _custom_1(self):
        """add CALMMAGE_ROOT_DIR and CALMMAGE_APP_DATA_DIR to env variables"""

        for line in [
            f"export CALMMAGE_ROOT_DIR={self.root_dir}",
            f"export CALMMAGE_APP_DATA_DIR={self.app_data_dir}",
        ]:
            self._source_line(line)

    @property
    def scripts_dir(self):
        return self.root_dir / self.preset.scripts_dir
        # return self.root_dir / 'workspace' / 'launchd' / 'scripts'

    def _copy_script(self, script_name, suffix=".py"):
        source_path = Path(__file__).parent / "tools" / (script_name + suffix)
        target_path = self.scripts_dir / (script_name + suffix)
        copyfile(source_path, target_path)

    def _custom_2(self):
        self._copy_script("daily_job")
        self._copy_script("monthly_job")

    def _custom_3(self):
        source_path = Path(__file__).parent / "tools" / "project_manager.py"
        target_path = self.app_data_dir / "project_manager.py"
        copyfile(source_path, target_path)

        # add to the .alias
        lines = [
            f"alias new_project='python3 {target_path} add'",
            f"alias np='python3 {target_path} add'",
            f"alias pm='python3 {target_path}'",
            f"alias project_manager='python3 {target_path}'\n",
        ]
        for line in lines:
            self._source_line(line, targets=[f"{self.app_data_dir}/.alias"])

    def _custom_4(self):
        # add aliases to the main dirs in the repo

        # add to the .alias
        aliases = {
            # latest dir
            self.seasonal_projects_dir / "latest": ["cd_1", "cdl", "cd_latest"],
            # playground
            self.root_dir / "playground": ["cd_2", "cdp", "cd_playground"],
            # structured
            self.root_dir / "code" / "structured": ["cd_3", "cds", "cd_structured"],
        }
        for target in aliases:
            for alias in aliases[target]:
                line = f"alias {alias}='cd {target}'"
                self._source_line(line, targets=[self.app_data_dir / ".alias"])

    def _custom_5(self):
        # improved help string
        pass
