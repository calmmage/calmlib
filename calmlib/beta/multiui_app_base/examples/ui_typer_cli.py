"""
Goal of this file:
given an app that has a simple text-based interface, we want to create a Typer CLI interface for it
app will have .invoke() method that takes a string and returns a string
"""

from calmlib.beta.multiui_app_base.ui_typer_cli import main
import typer

if __name__ == "__main__":
    typer.run(main)
