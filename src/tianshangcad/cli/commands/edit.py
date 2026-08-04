"""Editing commands: move, copy, rotate, scale, erase, list, undo, redo, boolean, param."""

from __future__ import annotations

import typer

from tianshangcad.cli.utils import (
    catch_errors,
    get_document,
    parse_point,
    push_undo,
    restore_document,
)
from tianshangcad.core.session import SessionManager
from tianshangcad.core.transform import rotation_around_point_z, scale_around_point, translation
from tianshangcad.utils.errors import VariableError

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
    from tianshangcad.cli.utils import snapshot_document

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
    from tianshangcad.cli.utils import snapshot_document

    current = snapshot_document(doc)
    restore_document(doc, after)
    session.undo_stack.append(current)
    typer.echo("Redone")


@app.command("union")
@catch_errors
def cmd_union(
    target: str = typer.Argument(..., help="Target object id"),
    tool: str = typer.Argument(..., help="Tool object id"),
    new_id: str | None = typer.Option(None, "--new-id", help="Id for the result"),
) -> None:
    """Union two objects into a new mesh."""
    doc = get_document()
    push_undo()
    result_id = doc.entities.boolean("union", target, tool, object_id=new_id)
    typer.echo(f"Union {target} + {tool} -> {result_id}")


@app.command("subtract")
@catch_errors
def cmd_subtract(
    target: str = typer.Argument(..., help="Target object id"),
    tool: str = typer.Argument(..., help="Tool object id"),
    new_id: str | None = typer.Option(None, "--new-id", help="Id for the result"),
) -> None:
    """Subtract tool object from target object."""
    doc = get_document()
    push_undo()
    result_id = doc.entities.boolean("subtract", target, tool, object_id=new_id)
    typer.echo(f"Subtract {tool} from {target} -> {result_id}")


@app.command("intersect")
@catch_errors
def cmd_intersect(
    target: str = typer.Argument(..., help="Target object id"),
    tool: str = typer.Argument(..., help="Tool object id"),
    new_id: str | None = typer.Option(None, "--new-id", help="Id for the result"),
) -> None:
    """Intersect two objects into a new object."""
    doc = get_document()
    push_undo()
    result_id = doc.entities.boolean("intersect", target, tool, object_id=new_id)
    typer.echo(f"Intersect {target} & {tool} -> {result_id}")


@app.command("param-set")
@catch_errors
def cmd_param_set(
    name: str = typer.Argument(..., help="Variable name"),
    value: float | None = typer.Argument(None, help="Numeric value (omit with --expr)"),
    unit: str = typer.Option("", "--unit", "-u", help="Unit suffix (e.g. mm)"),
    expr: str | None = typer.Option(None, "--expr", "-e", help="Arithmetic expression"),
) -> None:
    """Set a parametric variable (``{name}`` is interpolated in draw args)."""
    doc = get_document()
    push_undo()
    try:
        record = doc.variables.set(name, value=value, unit=unit, expr=expr)
    except VariableError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=1) from exc
    value_text = str(int(record.value)) if record.value.is_integer() else str(record.value)
    typer.echo(f"Set {name} = {value_text}{record.unit or ''}")


@app.command("param-list")
@catch_errors
def cmd_param_list() -> None:
    """List parametric variables."""
    doc = get_document()
    records = doc.variables.list()
    if not records:
        typer.echo("No variables")
        return
    for record in records:
        value_text = str(int(record.value)) if record.value.is_integer() else str(record.value)
        typer.echo(
            f"{record.name} = {value_text}{record.unit or ''}"
            + (f"  (expr: {record.expr})" if record.expr else "")
        )


@app.command("param-delete")
@catch_errors
def cmd_param_delete(
    name: str = typer.Argument(..., help="Variable name"),
) -> None:
    """Delete a parametric variable."""
    doc = get_document()
    push_undo()
    try:
        doc.variables.delete(name)
    except VariableError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Deleted {name}")
