"""Assembly commands: create, add parts, sub-assemblies, mates, solve, BOM, explode."""

from __future__ import annotations

import typer

from cad_mcp_server.cli.utils import catch_errors, get_document, parse_float, push_undo
from cad_mcp_server.core.assembly import AssemblyDocument

app = typer.Typer(help="Assembly modelling commands")


def _require_assembly() -> AssemblyDocument:
    return get_document().assembly()


def _echo_value(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


@app.command("create")
@catch_errors
def cmd_create(
    name: str = typer.Option("assembly", "--name", "-n", help="Assembly name"),
) -> None:
    """Create or re-open the assembly in the current document."""
    get_document().assembly(name)
    typer.echo(f"Assembly {name} ready")


@app.command("add-part")
@catch_errors
def cmd_add_part(
    name: str = typer.Argument(..., help="Part name"),
    entity_id: str | None = typer.Option(None, "--entity", "-e", help="Referenced entity id"),
    parent_id: str | None = typer.Option(None, "--parent", help="Parent node id"),
) -> None:
    """Add a part to the assembly."""
    push_undo()
    node_id = _require_assembly().add_part(
        name=name, entity_id=entity_id, parent_id=parent_id
    )
    parent = f" under {parent_id}" if parent_id else ""
    typer.echo(f"Added part {name} ({node_id}){parent}")


@app.command("add-subasm")
@catch_errors
def cmd_add_subasm(
    name: str = typer.Argument(..., help="Sub-assembly name"),
    parent_id: str | None = typer.Option(None, "--parent", help="Parent node id"),
) -> None:
    """Add a sub-assembly container."""
    push_undo()
    node_id = _require_assembly().add_subassembly(name=name, parent_id=parent_id)
    typer.echo(f"Added sub-assembly {name} ({node_id})")


@app.command("mate")
@catch_errors
def cmd_mate(
    node_a: str = typer.Argument(..., help="Anchor node id"),
    node_b: str = typer.Argument(..., help="Target node id"),
    mate_type: str = typer.Option(
        ..., "--type", "-t", help="coincident|concentric|parallel|perpendicular|distance|angle"
    ),
    distance: float | None = typer.Option(None, "--distance", "-d", help="Distance value"),
    angle: float | None = typer.Option(None, "--angle", "-a", help="Angle in degrees"),
    axis: str | None = typer.Option(None, "--axis", help="Axis 'x,y,z' for distance mates"),
) -> None:
    """Add a mate between two assembly nodes."""
    push_undo()
    params: dict[str, object] = {}
    if distance is not None:
        params["distance"] = distance
    if angle is not None:
        params["angle"] = angle
    if axis:
        parts = axis.split(",")
        if len(parts) != 3:
            typer.echo("Error: --axis must be 'x,y,z'", err=True)
            raise typer.Exit(code=1)
        params["axis"] = [parse_float(part) for part in parts]
    mate_id = _require_assembly().add_mate(mate_type, node_a, node_b, params)
    typer.echo(f"Added {mate_type} mate {mate_id} ({node_a} -> {node_b})")


@app.command("solve")
@catch_errors
def cmd_solve() -> None:
    """Solve the assembly and print world transforms."""
    assembly = _require_assembly()
    if not assembly.mates:
        typer.echo("No mates to solve")
        return
    push_undo()
    transforms = assembly.solve()
    for node_id, world in transforms.items():
        t = world["translation"]
        typer.echo(
            f"{node_id}  t=({_echo_value(t[0])}, {_echo_value(t[1])}, "
            f"{_echo_value(t[2])})"
        )
    typer.echo(f"Solved {len(assembly.mates)} mates")


@app.command("bom")
@catch_errors
def cmd_bom(
    csv: bool = typer.Option(False, "--csv", help="Output comma-separated text"),
) -> None:
    """Print the bill of materials."""
    assembly = _require_assembly()
    rows = assembly.bom()
    if not rows:
        typer.echo("No parts in assembly")
        return
    if csv:
        typer.echo(assembly.bom_csv().strip())
        return
    for row in rows:
        typer.echo(f"{row['name']:24s} x{row['quantity']}")


@app.command("explode")
@catch_errors
def cmd_explode(
    spacing: float = typer.Option(10.0, "--spacing", "-s", help="Offset per level"),
    direction: str = typer.Option("x", "--direction", "-d", help="x, y or z"),
) -> None:
    """Print exploded-view offsets for the assembly."""
    assembly = _require_assembly()
    records = assembly.explode(spacing=spacing, direction=direction)
    for record in records:
        t = record["translation"]
        typer.echo(
            f"{record['node_id']}  depth={record['depth']}  "
            f"t=({_echo_value(t[0])}, {_echo_value(t[1])}, {_echo_value(t[2])})"
        )
