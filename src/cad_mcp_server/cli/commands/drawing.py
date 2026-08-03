"""Drawing commands: create, add views, sections, dimensions, GD&T, export."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from cad_mcp_server.cli.utils import catch_errors, get_document, parse_float, push_undo
from cad_mcp_server.core.drawing import DrawingDocument

app = typer.Typer(help="Engineering drawing commands")


def _require_drawing() -> DrawingDocument:
    return get_document().drawing()


def _records() -> dict[str, Any]:
    doc = get_document()
    return {record.id: record for record in doc.entities.list()}


@app.command("create")
@catch_errors
def cmd_create(
    name: str = typer.Option("drawing", "--name", "-n", help="Drawing name"),
    paper: str = typer.Option("A4", "--paper", "-p", help="A0/A1/A2/A3/A4"),
    title: str = typer.Option("", "--title", help="Title block title"),
) -> None:
    """Create or re-open the drawing sheet in the current document."""
    drawing = get_document().drawing(paper=paper, title=title)
    drawing.name = name
    typer.echo(f"Drawing {name} ready ({drawing.paper}, {drawing.width:g}x{drawing.height:g} mm)")


@app.command("add-view")
@catch_errors
def cmd_add_view(
    name: str = typer.Argument(..., help="View name"),
    view_type: str = typer.Argument(..., help="main|projection|section|detail|isometric"),
    scale: float = typer.Option(1.0, "--scale", "-s", help="View scale"),
    direction: str = typer.Option("front", "--direction", "-d", help="top/front/side"),
    entity_ids: str | None = typer.Option(None, "--entities", help="Comma-separated entity ids"),
) -> None:
    """Add a view to the drawing sheet."""
    push_undo()
    ids = [part.strip() for part in entity_ids.split(",")] if entity_ids else None
    view_id = _require_drawing().add_view(
        name=name,
        view_type=view_type,
        scale=scale,
        direction=direction,
        entity_ids=ids,
    )
    typer.echo(f"Added {view_type} view {name} ({view_id})")


@app.command("section")
@catch_errors
def cmd_section(
    name: str = typer.Argument(..., help="Section view name"),
    plane: str = typer.Option("XZ", "--plane", "-p", help="XY/YZ/XZ"),
    offset: float = typer.Option(0.0, "--offset", "-o", help="Plane offset"),
) -> None:
    """Add a section view to the drawing sheet."""
    push_undo()
    view_id = _require_drawing().add_section(
        name=name, plane=plane, offset=offset
    )
    typer.echo(f"Added section view {name} ({view_id})")


@app.command("dim")
@catch_errors
def cmd_dim(
    dim_type: str = typer.Argument(..., help="linear|angular|radial|diameter|ordinate"),
    value: str = typer.Argument(..., help="Dimension value"),
) -> None:
    """Add an ISO 129-1 dimension."""
    push_undo()
    dim_id = _require_drawing().add_dimension(
        dim_type=dim_type, value=parse_float(value)
    )
    typer.echo(f"Added {dim_type} dimension {value} ({dim_id})")


@app.command("gdt")
@catch_errors
def cmd_gdt(
    symbol: str = typer.Argument(
        ..., help="position|flatness|parallelism|perpendicularity|concentricity"
    ),
    value: str | None = typer.Option(None, "--value", "-v", help="Tolerance value"),
    datum: str | None = typer.Option(None, "--datum", "-d", help="Datum reference"),
) -> None:
    """Add a GD&T feature-control frame."""
    push_undo()
    gdt_id = _require_drawing().add_tolerance(
        symbol=symbol,
        value=parse_float(value) if value is not None else None,
        datum=datum,
    )
    gdt = _require_drawing().get_tolerance(gdt_id)
    typer.echo(f"Added GD&T {gdt.label} ({gdt_id})")


@app.command("export")
@catch_errors
def cmd_export(
    output_format: str = typer.Argument(..., help="svg|dxf|pdf"),
    path: str = typer.Argument(..., help="Target file path"),
) -> None:
    """Export the drawing to an SVG, DXF or PDF file."""
    drawing = _require_drawing()
    records = _records()
    kernel = get_document().entities.kernel
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True) if target.parent else None
    fmt = output_format.lower()
    if fmt == "svg":
        drawing.export_svg(records, str(target), kernel)
    elif fmt == "dxf":
        drawing.export_dxf(records, str(target), kernel)
    elif fmt == "pdf":
        drawing.export_pdf(records, str(target), kernel)
    else:
        typer.echo(f"Error: unsupported export format {output_format!r}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Exported {fmt.upper()} to {target}")
