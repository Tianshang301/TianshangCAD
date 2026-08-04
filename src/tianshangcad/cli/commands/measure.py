"""Measurement tools: distance, area, list."""

from __future__ import annotations

import math
from typing import Any

import typer

from tianshangcad.cli.utils import catch_errors, get_document, parse_point
from tianshangcad.utils.errors import EntityError

app = typer.Typer(help="Measurement tools")


@app.command("distance")
@catch_errors
def cmd_distance(
    point_a: str = typer.Argument(..., help="First point x,y[,z]"),
    point_b: str = typer.Argument(..., help="Second point x,y[,z]"),
) -> None:
    """Measure the distance between two points."""
    a = parse_point(point_a)
    b = parse_point(point_b)
    distance = math.dist(a, b)
    typer.echo(f"Distance: {distance:.6f} mm")


@app.command("area")
@catch_errors
def cmd_area(
    entity_id: str = typer.Argument(..., help="Object id"),
) -> None:
    """Measure the area of a 2D object (or volume of a solid)."""
    doc = get_document()
    record = doc.entities.get(entity_id)
    params = record.shape["params"]
    if record.type == "circle":
        value = math.pi * params["radius"] ** 2
        label = "Area"
    elif record.type == "rectangle":
        value = params["width"] * params["height"]
        label = "Area"
    elif record.type == "polygon":
        n = params["sides"]
        value = 0.5 * n * params["radius"] ** 2 * math.sin(2 * math.pi / n)
        label = "Area"
    elif record.type in ("box", "cylinder", "sphere", "cone"):
        value = _solid_volume(record.type, params)
        label = "Volume"
    else:
        raise EntityError(
            f"No area defined for type {record.type!r}", code="unsupported_measure"
        )
    typer.echo(f"{label}: {value:.6f} mm^2" if label == "Area" else f"{label}: {value:.6f} mm^3")


@app.command("list")
@catch_errors
def cmd_list() -> None:
    """Measure all objects and print their bboxes."""
    doc = get_document()
    records = doc.entities.list()
    if not records:
        typer.echo("No objects")
        return
    for record in records:
        bbox = doc.entities.get_bbox(record.id)
        typer.echo(f"{record.id}  {record.type:10s}  min={bbox['min']}  max={bbox['max']}")


def _solid_volume(kind: str, params: dict[str, Any]) -> float:
    if kind == "box":
        x, y, z = params["dimensions"]
        return float(x * y * z)
    if kind == "cylinder":
        return float(math.pi * params["radius"] ** 2 * params["height"])
    if kind == "sphere":
        return float(4.0 / 3.0 * math.pi * params["radius"] ** 3)
    if kind == "cone":
        rb, rt = params["radius_bottom"], params["radius_top"]
        return float(
            math.pi * params["height"] / 3.0 * (rb**2 + rt**2 + rb * rt)
        )
    raise EntityError(f"No volume defined for {kind}", code="unsupported_measure")
