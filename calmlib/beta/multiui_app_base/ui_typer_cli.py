"""
Goal of this file:
given an app that has a simple text-based interface, we want to create a Typer CLI interface for it
app will have .invoke() method that takes a string and returns a string
"""
from app import App
import typer

app = App()

def main(input_str: str = typer.Argument(..., help="The input string to be passed to the app"),
          continuous: bool = typer.Option(False, "--continuous", "-c", help="Run the app continuously")):
    output_str = app.invoke(input_str)
    typer.echo(output_str)
    if continuous:
        while True:
            input_str = typer.prompt("Enter your input")
            if input_str.lower() == 'quit':
                break
            output_str = app.invoke(input_str)
            typer.echo(output_str)

if __name__ == '__main__':
    typer.run(main)
