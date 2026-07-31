"""Editing commands: move, copy, rotate, scale, erase, list, undo, redo."""

from __future__ import annotations

import typer

from cad_mcp_server.cli.utils import (
    catch_errors,
    get_document,
    parse_point,
    push_undo,
    restore_document,
)
from cad_mcp_server.core.session import SessionManager
from cad_mcp_server.core.transform import rotation_around_point_z, scale_around_point, translation

app = typer.Typer(help="Editing commands")


@app.command("move")
@catch_errors
def cmd_move(
    entity_id: str = typer.Argument(..., help="Object id"),
    dx: float = typer.Option(0.0, "--dx", help="Delta x"),
    dy: float = typer.Option(0.0, "--dy", help="Delta y"),
    dz: float = typer.Option(0.0, "--dz", help="Delta z"),
) -> None:
    """Move an object by an offset."""
    doc = get_document()
    push_undo()
    doc.entities.transform(entity_id, translation(dx, dy, dz))
    typer.echo(f"Moved {entity_id} by ({dx}, {dy}, {dz})")


@app.command("copy")
@catch_errors
def cmd_copy(
    entity_id: str = typer.Argument(..., help="Object id"),
    new_id: str | None = typer.Option(None, "--new-id", help="Id for the copy"),
) -> None:
    """Copy an object."""
    doc = get_document()
    push_undo()
    target_id = doc.entities.copy(entity_id, new_id=new_id)
    typer.echo(f"Copied {entity_id} -> {target_id}")


@app.command("rotate")
@catch_errors
def cmd_rotate(
    entity_id: str = typer.Argument(..., help="Object id"),
    angle: float = typer.Option(..., "--angle", help="Rotation angle (degrees)"),
    center: str = typer.Option("0,0,0", "--center", "-c", help="Rotation centre x,y,z"),
) -> None:
    """Rotate an object about the Z axis around a centre point."""
    doc = get_document()
    push_undo()
    matrix = rotation_around_point_z(angle, parse_point(center))
    doc.entities.transform(entity_id, matrix)
    typer.echo(f"Rotated {entity_id} by {angle} degrees")


@app.command("scale")
@catch_errors
def cmd_scale(
    entity_id: str = typer.Argument(..., help="Object id"),
    factor: float = typer.Option(..., "--factor", "-f", help="Scale factor"),
    center: str = typer.Option("0,0,0", "--center", "-c", help="Scale centre x,y,z"),
) -> None:
    """Scale an object about a centre point."""
    doc = get_document()
    push_undo()
    matrix = scale_around_point(factor, parse_point(center))
    doc.entities.transform(entity_id, matrix)
    typer.echo(f"Scaled {entity_id} by {factor}")


@app.command("erase")
@catch_errors
def cmd_erase(
    entity_id: str = typer.Argument(..., help="Object id"),
) -> None:
    """Erase an object."""
    doc = get_document()
    push_undo()
    doc.entities.delete(entity_id)
    typer.echo(f"Erased {entity_id}")


@app.command("list")
@catch_errors
def cmd_list(
    layer: str | None = typer.Option(None, "--layer", "-l", help="Filter by layer"),
) -> None:
    """List objects."""
    doc = get_document()
    records = doc.entities.list(layer=layer)
    if not records:
        typer.echo("No objects")
        return
    for record in records:
        bbox = doc.entities.get_bbox(record.id)
        typer.echo(
            f"{record.id}  {record.type:10s}  layer={record.layer}  "
            f"min={bbox['min']}  max={bbox['max']}"
        )


@app.command("undo")
@catch_errors
def cmd_undo() -> None:
    """Undo the last editing operation."""
    doc = get_document()
    session = SessionManager().current_session
    if not session.undo_stack:
        typer.echo("Nothing to undo")
        return
    before = session.undo_stack.pop()
    from cad_mcp_server.cli.utils import snapshot_document

    current = snapshot_document(doc)
    restore_document(doc, before)
    session.redo_stack.append(current)
    typer.echo("Undone")


@app.command("redo")
@catch_errors
def cmd_redo() -> None:
    """Redo the last undone operation."""
    doc = get_document()
    session = SessionManager().current_session
    if not session.redo_stack:
        typer.echo("Nothing to redo")
        return
    after = session.redo_stack.pop()
    from cad_mcp_server.cli.utils import snapshot_document

    current = snapshot_document(doc)
    restore_document(doc, after)
    session.undo_stack.append(current)
    typer.echo("Redone")
