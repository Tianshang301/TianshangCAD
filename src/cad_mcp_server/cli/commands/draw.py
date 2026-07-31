"""Drawing commands: line, circle, arc, rectangle, polygon, polyline, box, cylinder, sphere."""

from __future__ import annotations

from typing import Any

import typer

from cad_mcp_server.cli.utils import catch_errors, get_document, parse_point

app = typer.Typer(help="Drawing commands")


def _echo_created(entity_id: str) -> None:
    typer.echo(f"Created {entity_id}")


@app.command("line")
@catch_errors
def cmd_line(
    start: str = typer.Argument(..., help="Start point x,y[,z]"),
    end: str = typer.Argument(..., help="End point x,y[,z]"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a line segment."""
    doc = get_document()
    entity_id = doc.entities.create(
        "line", {"start": parse_point(start), "end": parse_point(end)}, layer=layer
    )
    _echo_created(entity_id)


@app.command("circle")
@catch_errors
def cmd_circle(
    center: str = typer.Argument(..., help="Center point x,y[,z]"),
    radius: float = typer.Option(..., "--radius", "-r", help="Radius"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a circle."""
    doc = get_document()
    entity_id = doc.entities.create(
        "circle", {"center": parse_point(center), "radius": radius}, layer=layer
    )
    _echo_created(entity_id)


@app.command("arc")
@catch_errors
def cmd_arc(
    center: str = typer.Argument(..., help="Center point x,y[,z]"),
    radius: float = typer.Option(..., "--radius", "-r", help="Radius"),
    start_angle: float = typer.Option(0.0, "--start-angle", help="Start angle (degrees)"),
    end_angle: float = typer.Option(180.0, "--end-angle", help="End angle (degrees)"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a circular arc."""
    doc = get_document()
    entity_id = doc.entities.create(
        "arc",
        {
            "center": parse_point(center),
            "radius": radius,
            "start_angle": start_angle,
            "end_angle": end_angle,
        },
        layer=layer,
    )
    _echo_created(entity_id)


@app.command("rectangle")
@catch_errors
def cmd_rectangle(
    origin: str = typer.Argument(..., help="Origin corner x,y[,z]"),
    width: float = typer.Option(..., "--width", "-w", help="Width"),
    height: float = typer.Option(..., "--height", "-h", help="Height"),
    rotation: float = typer.Option(0.0, "--rotation", help="Rotation (degrees)"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a rectangle."""
    doc = get_document()
    entity_id = doc.entities.create(
        "rectangle",
        {
            "origin": parse_point(origin),
            "width": width,
            "height": height,
            "rotation": rotation,
        },
        layer=layer,
    )
    _echo_created(entity_id)


@app.command("polygon")
@catch_errors
def cmd_polygon(
    center: str = typer.Argument(..., help="Center point x,y[,z]"),
    radius: float = typer.Option(..., "--radius", "-r", help="Circumradius"),
    sides: int = typer.Option(..., "--sides", "-s", help="Number of sides"),
    rotation: float = typer.Option(0.0, "--rotation", help="Rotation (degrees)"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a regular polygon."""
    doc = get_document()
    entity_id = doc.entities.create(
        "polygon",
        {
            "center": parse_point(center),
            "radius": radius,
            "sides": sides,
            "rotation": rotation,
        },
        layer=layer,
    )
    _echo_created(entity_id)


@app.command("polyline")
@catch_errors
def cmd_polyline(
    points: str = typer.Argument(..., help="Space separated points, e.g. \"0,0 10,0 10,10\""),
    closed: bool = typer.Option(False, "--closed", help="Close the polyline"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a polyline through the given points."""
    from cad_mcp_server.utils.validators import parse_point_list

    doc = get_document()
    entity_id = doc.entities.create(
        "polyline", {"points": parse_point_list(points), "closed": closed}, layer=layer
    )
    _echo_created(entity_id)


@app.command("box")
@catch_errors
def cmd_box(
    origin: str = typer.Argument(..., help="Origin x,y,z"),
    dimensions: str = typer.Option(..., "--dimensions", "-d", help="Dimensions x,y,z"),
    rotation: str | None = typer.Option(None, "--rotation", help="1 or 3 angles (degrees)"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a 3D box."""
    from cad_mcp_server.utils.validators import parse_point as parse_dims

    doc = get_document()
    params: dict[str, Any] = {
        "origin": parse_point(origin),
        "dimensions": parse_dims(dimensions),
    }
    if rotation is not None:
        params["rotation"] = parse_dims(rotation)
    entity_id = doc.entities.create("box", params, layer=layer)
    _echo_created(entity_id)


@app.command("cylinder")
@catch_errors
def cmd_cylinder(
    origin: str = typer.Argument(..., help="Base centre x,y,z"),
    radius: float = typer.Option(..., "--radius", "-r", help="Radius"),
    height: float = typer.Option(..., "--height", "-h", help="Height"),
    axis: str = typer.Option("0,0,1", "--axis", help="Axis x,y,z"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a cylinder."""
    doc = get_document()
    entity_id = doc.entities.create(
        "cylinder",
        {
            "origin": parse_point(origin),
            "radius": radius,
            "height": height,
            "axis": parse_point(axis),
        },
        layer=layer,
    )
    _echo_created(entity_id)


@app.command("sphere")
@catch_errors
def cmd_sphere(
    center: str = typer.Argument(..., help="Centre point x,y,z"),
    radius: float = typer.Option(..., "--radius", "-r", help="Radius"),
    layer: str = typer.Option("0", "--layer", "-l", help="Target layer"),
) -> None:
    """Draw a sphere."""
    doc = get_document()
    entity_id = doc.entities.create(
        "sphere", {"center": parse_point(center), "radius": radius}, layer=layer
    )
    _echo_created(entity_id)
