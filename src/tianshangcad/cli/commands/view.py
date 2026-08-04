"""View control commands: zoom, pan, list."""

from __future__ import annotations

import typer

from tianshangcad.cli.utils import catch_errors, get_document, push_undo
from tianshangcad.core.document import DocumentManager
from tianshangcad.core.transform import translation

app = typer.Typer(help="View control")


@app.command("zoom")
@catch_errors
def cmd_zoom(
    extents: bool = typer.Option(False, "--extents", help="Zoom to drawing extents"),
) -> None:
    """Zoom control (currently prints extents)."""
    if not extents:
        typer.echo("Use --extents to show drawing extents")
        return
    doc_mgr = DocumentManager()
    info = doc_mgr.info()
    bbox = info["bbox"]
    typer.echo(f"Extents: min={bbox['min']}  max={bbox['max']}")


@app.command("pan")
@catch_errors
def cmd_pan(
    dx: float = typer.Option(0.0, "--dx", help="Pan x"),
    dy: float = typer.Option(0.0, "--dy", help="Pan y"),
) -> None:
    """Pan all objects by an offset."""
    doc = get_document()
    if dx == 0 and dy == 0:
        typer.echo("Nothing to pan")
        return
    push_undo()
    matrix = translation(dx, dy, 0)
    for record in doc.entities.list():
        doc.entities.transform(record.id, matrix)
    typer.echo(f"Panned all objects by ({dx}, {dy})")


@app.command("list")
@catch_errors
def cmd_list() -> None:
    """List objects in the drawing order."""
    doc = get_document()
    records = doc.entities.list()
    if not records:
        typer.echo("No objects")
        return
    for record in records:
        typer.echo(f"{record.id}  {record.type}  layer={record.layer}")
