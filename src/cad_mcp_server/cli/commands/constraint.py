"""Constraint commands: add, remove, list, solve."""

from __future__ import annotations

import typer

from cad_mcp_server.cli.utils import catch_errors, get_document, push_undo
from cad_mcp_server.core.constraint import ConstraintType
from cad_mcp_server.core.solver import apply_solution, solve_2d
from cad_mcp_server.utils.errors import CADError

app = typer.Typer(help="Geometric constraint commands")


def _parse_type(value: str) -> ConstraintType:
    try:
        return ConstraintType(value.lower())
    except ValueError:
        supported = ", ".join(t.value for t in ConstraintType)
        typer.echo(
            f"Error: unsupported constraint type {value!r}; supported: {supported}",
            err=True,
        )
        raise typer.Exit(code=1) from None


def _echo_value(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


@app.command("add")
@catch_errors
def cmd_add(
    entity_a: str = typer.Argument(..., help="First entity id"),
    entity_b: str = typer.Argument(..., help="Second entity id"),
    ctype_name: str = typer.Option(
        ..., "--type", "-t", help="Constraint type (parallel, tangent, ...)"
    ),
    distance: float | None = typer.Option(None, "--distance", "-d", help="Target distance"),
    angle: float | None = typer.Option(None, "--angle", "-a", help="Target angle (degrees)"),
) -> None:
    """Add a geometric constraint between two entities."""
    ctype = _parse_type(ctype_name)
    doc = get_document()
    push_undo()
    params: dict[str, float] = {}
    if distance is not None:
        params["distance"] = distance
    if angle is not None:
        params["angle"] = angle
    record = doc.constraints.add(ctype, [entity_a, entity_b], params)
    detail = ""
    if params:
        pieces = [f"{key}={_echo_value(value)}" for key, value in params.items()]
        detail = f" ({', '.join(pieces)})"
    typer.echo(f"Added {ctype.value} constraint {record.id} on {entity_a}, {entity_b}{detail}")


@app.command("remove")
@catch_errors
def cmd_remove(
    constraint_id: str = typer.Argument(..., help="Constraint id"),
) -> None:
    """Remove a geometric constraint."""
    doc = get_document()
    push_undo()
    doc.constraints.remove(constraint_id)
    typer.echo(f"Removed constraint {constraint_id}")


@app.command("list")
@catch_errors
def cmd_list(
    entity_id: str | None = typer.Option(None, "--entity", help="Filter by entity id"),
) -> None:
    """List geometric constraints."""
    doc = get_document()
    records = doc.constraints.list(entity_id=entity_id)
    if not records:
        typer.echo("No constraints")
        return
    for record in records:
        params = record.params
        param_text = f"  {params}" if params else ""
        typer.echo(
            f"{record.id}  {record.type.value:12s}  {', '.join(record.entities)}{param_text}"
        )


@app.command("solve")
@catch_errors
def cmd_solve() -> None:
    """Solve the constraint system and write back geometry."""
    doc = get_document()
    constraints = doc.constraints.list()
    if not constraints:
        typer.echo("No constraints to solve")
        return
    push_undo()
    try:
        records = {
            entity_id: doc.entities.get(entity_id)
            for constraint in constraints
            for entity_id in constraint.entities
        }
        result = solve_2d(records, constraints)
    except CADError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=1) from exc
    if result.converged:
        apply_solution(doc.entities, result)
        doc.touch()
        moved = ", ".join(sorted(result.updates)) if result.updates else "(none)"
        typer.echo(
            f"Solved {len(constraints)} constraints in {result.iterations} iterations "
            f"(residual {result.residual_norm:.3e}); moved: {moved}"
        )
    else:
        typer.echo(
            f"Error: {result.message} (iterations {result.iterations})", err=True
        )
        raise typer.Exit(code=1)
