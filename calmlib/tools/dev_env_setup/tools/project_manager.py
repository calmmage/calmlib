from calmlib.tools.dev_env_setup.dev_env import DEFAULT_ROOT_DIR
from calmlib.tools.dev_env_setup.dev_env import CalmmageDevEnv
import typer


app = typer.Typer("Calmmage Project Manager")


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
    name: str,
    template_name: str,
    local: bool = True,
    root_dir: str = DEFAULT_ROOT_DIR,
    app_data_dir: str = DEFAULT_ROOT_DIR,
):
    dev_env = CalmmageDevEnv(root_dir, app_data_dir)

    project_dir = dev_env.start_new_project(
        name, local=local, template_name=template_name
    )

    # todo: change the dir to new project? or just print the path?
    typer.echo(project_dir)


if __name__ == "__main__":
    app()
