"""Feature commands: sweep, loft, fillet, chamfer and patterns.

Arguments support ``{name}`` interpolation against the current
document's parametric variables (e.g. ``--radius {r}``).
"""

from __future__ import annotations

from typing import Any

import typer

from cad_mcp_server.cli.utils import (
    catch_errors,
    get_document,
    interpolate,
    parse_float,
    parse_point,
    parse_point_list,
    push_undo,
)

app = typer.Typer(help="Parametric feature commands")


def _require_features() -> Any:
    return get_document().features()


def _echo_value(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


def _echo_point(point: list[float]) -> str:
    return f"({', '.join(_echo_value(value) for value in point)})"


@app.command("sweep")
@catch_errors
def cmd_sweep(
    profile_id: str = typer.Argument(..., help="Profile entity id (circle/rectangle)"),
    path: str = typer.Argument(..., help="Space separated path points, e.g. '0,0,0 0,0,20'"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Sweep a profile along a polyline path."""
    push_undo()
    object_id = _require_features().sweep(
        profile_id, parse_point_list(path), layer=layer
    )
    typer.echo(f"Sweep created {object_id}")


@app.command("loft")
@catch_errors
def cmd_loft(
    profile_ids: str = typer.Argument(..., help="Comma separated profile ids"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Loft between stacked profiles."""
    push_undo()
    ids = [item.strip() for item in interpolate(profile_ids).split(",")]
    object_id = _require_features().loft(ids, layer=layer)
    typer.echo(f"Loft created {object_id}")


@app.command("fillet")
@catch_errors
def cmd_fillet(
    entity_id: str = typer.Argument(..., help="Source entity id"),
    radius: str = typer.Argument(..., help="Fillet radius"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Blend an entity's edges with a fillet (requires OCCT kernel)."""
    push_undo()
    object_id = _require_features().fillet(
        entity_id, parse_float(radius), layer=layer
    )
    typer.echo(f"Fillet created {object_id}")


@app.command("chamfer")
@catch_errors
def cmd_chamfer(
    entity_id: str = typer.Argument(..., help="Source entity id"),
    size: str = typer.Argument(..., help="Chamfer size"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Cut an entity's edges with a chamfer (requires OCCT kernel)."""
    push_undo()
    object_id = _require_features().chamfer(
        entity_id, parse_float(size), layer=layer
    )
    typer.echo(f"Chamfer created {object_id}")


@app.command("pattern")
@catch_errors
def cmd_pattern(
    entity_id: str = typer.Argument(..., help="Source entity id"),
    kind: str = typer.Option(
        ..., "--kind", "-k", help="linear | circular | mirror"
    ),
    count: int | None = typer.Option(None, "--count", "-n", help="Instance count"),
    spacing: str | None = typer.Option(None, "--spacing", "-s", help="Linear spacing"),
    direction: str | None = typer.Option(
        None, "--direction", "-d", help="Linear direction 'x,y,z'"
    ),
    center: str | None = typer.Option(None, "--center", "-c", help="Circular centre 'x,y,z'"),
    axis: str | None = typer.Option(None, "--axis", "-a", help="Circular axis 'x,y,z'"),
    angle: str | None = typer.Option(None, "--angle", help="Circular angular span (degrees)"),
    plane_point: str | None = typer.Option(None, "--point", help="Mirror plane point 'x,y,z'"),
    plane_normal: str | None = typer.Option(
        None, "--normal", help="Mirror plane normal 'x,y,z'"
    ),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Copy an entity with a linear, circular or mirror pattern."""
    push_undo()
    features = _require_features()
    kind_lower = kind.lower()
    if kind_lower == "linear":
        if count is None or spacing is None or direction is None:
            typer.echo("Error: linear requires --count, --spacing and --direction", err=True)
            raise typer.Exit(code=1)
        ids = features.pattern_linear(
            entity_id,
            parse_point(direction),
            count,
            parse_float(spacing),
            layer=layer,
        )
        typer.echo(f"Linear pattern produced {len(ids)} instances: {', '.join(ids)}")
    elif kind_lower == "circular":
        if count is None or center is None or axis is None:
            typer.echo("Error: circular requires --count, --center and --axis", err=True)
            raise typer.Exit(code=1)
        ids = features.pattern_circular(
            entity_id,
            parse_point(center),
            parse_point(axis),
            count,
            angle=parse_float(angle) if angle else 360.0,
            layer=layer,
        )
        typer.echo(f"Circular pattern produced {len(ids)} instances: {', '.join(ids)}")
    elif kind_lower == "mirror":
        if plane_point is None or plane_normal is None:
            typer.echo("Error: mirror requires --point and --normal", err=True)
            raise typer.Exit(code=1)
        object_id = features.pattern_mirror(
            entity_id, parse_point(plane_point), parse_point(plane_normal), layer=layer
        )
        typer.echo(f"Mirror created {object_id}")
    else:
        typer.echo("Error: --kind must be linear, circular or mirror", err=True)
        raise typer.Exit(code=1)
