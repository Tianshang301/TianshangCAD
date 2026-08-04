"""CLI root command application."""

from __future__ import annotations

import sys

import typer

from tianshangcad import __version__
from tianshangcad.cli.aliases import COMMAND_ALIASES
from tianshangcad.cli.commands import (
    assembly,
    batch,
    block,
    collab,
    constraint,
    draw,
    drawing,
    edit,
    features,
    file,
    layer,
    measure,
    render,
    simulation,
    view,
)
from tianshangcad.utils.logger import configure_logging

app = typer.Typer(
    name="tianshangcad",
    help="CAD CLI System - Command-line CAD operation tool",
    no_args_is_help=True,
    add_completion=False,
)

app.add_typer(file.app, name="file", help="File operations")
app.add_typer(draw.app, name="draw", help="Drawing commands")
app.add_typer(edit.app, name="edit", help="Editing commands")
app.add_typer(view.app, name="view", help="View control")
app.add_typer(measure.app, name="measure", help="Measurement tools")
app.add_typer(layer.app, name="layer", help="Layer management")
app.add_typer(block.app, name="block", help="Blocks and parametrics")
app.add_typer(render.app, name="render", help="Rendering output")
app.add_typer(batch.app, name="batch", help="Batch processing")
app.add_typer(constraint.app, name="constraint", help="Geometric constraints")
app.add_typer(assembly.app, name="assembly", help="Assembly modelling")
app.add_typer(drawing.app, name="drawing", help="Engineering drawings")
app.add_typer(features.app, name="feature", help="Parametric features")
app.add_typer(simulation.app, name="sim", help="Simulation interface")
app.add_typer(collab.app, name="collab", help="Real-time collaboration")


@app.callback()
def global_options(
    version: bool = typer.Option(
        False, "--version", help="Show version and exit"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config: str = typer.Option(
        "~/.tianshangcad/config.yaml", "--config", "-c", help="Config file path"
    ),
) -> None:
    """Global options."""
    if version:
        typer.echo(f"tianshangcad {__version__}")
        raise typer.Exit()
    if verbose:
        configure_logging(level="DEBUG")


def main() -> None:
    """Entry point that expands short command aliases then runs the app."""
    args = list(sys.argv[1:])
    if args and args[0] == "--version":
        typer.echo(f"tianshangcad {__version__}")
        raise SystemExit(0)
    if args and args[0] in COMMAND_ALIASES:
        args = COMMAND_ALIASES[args[0]].split() + args[1:]
        sys.argv = [sys.argv[0], *args]
    app()


if __name__ == "__main__":
    main()
