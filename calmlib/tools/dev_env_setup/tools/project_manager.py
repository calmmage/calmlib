from calmlib.tools.dev_env_setup.dev_env import DEFAULT_ROOT_DIR
from calmlib.tools.dev_env_setup.dev_env import CalmmageDevEnv
import typer
from typing_extensions import Annotated


app = typer.Typer(name="Calmmage Project Manager")

dev_env = CalmmageDevEnv()
local_templates = dev_env.get_local_template_names()
try:
    github_templates = dev_env.get_github_template_names()
except:
    github_templates = []
templates_prompt = (
    "Which template do you want to use? "
    "Local: " + ", ".join(local_templates) + " "
    "Github: " + ", ".join(github_templates)
)


@app.command(name="lt")
def list_templates(
    local: bool = True,
    root_dir: str = DEFAULT_ROOT_DIR,
    app_data_dir: str = DEFAULT_ROOT_DIR,
):
    dev_env = CalmmageDevEnv(root_dir, app_data_dir)
    dev_env.list_templates(local=local)


@app.command(name="add")
def add_new_project(
    name: Annotated[
        str,
        typer.Option(
            prompt="Name (What do you want the project to do?)\nName",
        ),
    ],
    template: Annotated[
        str,
        typer.Option(prompt=templates_prompt),
    ],
    # template_name: Annotated[
    #     str, typer.Option(prompt=templates_prompt, default="default")
    # ],
    local: bool = True,
    root_dir: str = DEFAULT_ROOT_DIR,
    app_data_dir: str = DEFAULT_ROOT_DIR,
):
    # todo: local: Annotated[bool, typer.Option(default=True, prompt=True)],
    dev_env = CalmmageDevEnv(root_dir, app_data_dir)

    project_dir = dev_env.start_new_project(name, local=local, template_name=template)

    # todo: change the dir to new project? or just print the path?
    typer.echo(project_dir)


if __name__ == "__main__":
    app()
