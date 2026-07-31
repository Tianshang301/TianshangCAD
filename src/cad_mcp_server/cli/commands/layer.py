"""Layer management commands."""

from __future__ import annotations

import typer

from cad_mcp_server.cli.utils import catch_errors, get_document

app = typer.Typer(help="Layer management")


@app.command("create")
@catch_errors
def cmd_create(
    name: str = typer.Argument(..., help="Layer name"),
    color: str = typer.Option("#FFFFFF", "--color", help="Color #RRGGBB"),
    linetype: str = typer.Option("Continuous", "--linetype", help="Line type"),
    linewidth: float = typer.Option(0.25, "--linewidth", help="Line width"),
) -> None:
    """Create a new layer."""
    doc = get_document()
    doc.layers.create(name=name, color=color, linetype=linetype, linewidth=linewidth)
    typer.echo(f"Layer created: {name}")


@app.command("list")
@catch_errors
def cmd_list() -> None:
    """List layers."""
    doc = get_document()
    current = doc.layers.get_current().name
    for layer in doc.layers.list():
        mark = "*" if layer.name == current else " "
        visibility = "on" if layer.visible else "off"
        typer.echo(f"{mark} {layer.name:15s} {layer.color:8s} {visibility}")


@app.command("set")
@catch_errors
def cmd_set(
    name: str = typer.Argument(..., help="Layer name"),
) -> None:
    """Set the current layer."""
    doc = get_document()
    doc.layers.set_current(name)
    typer.echo(f"Current layer: {name}")


@app.command("on")
@catch_errors
def cmd_on(
    name: str = typer.Argument(..., help="Layer name"),
) -> None:
    """Turn a layer on."""
    doc = get_document()
    doc.layers.update(name, visible=True)
    typer.echo(f"Layer on: {name}")


@app.command("off")
@catch_errors
def cmd_off(
    name: str = typer.Argument(..., help="Layer name"),
) -> None:
    """Turn a layer off."""
    doc = get_document()
    doc.layers.update(name, visible=False)
    typer.echo(f"Layer off: {name}")


@app.command("delete")
@catch_errors
def cmd_delete(
    name: str = typer.Argument(..., help="Layer name"),
) -> None:
    """Delete a layer."""
    doc = get_document()
    doc.layers.delete(name)
    typer.echo(f"Layer deleted: {name}")
