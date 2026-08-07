"""Measurement MCP tools: distance, area and volume."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import CADError, EntityError


class MeasureDistanceInput(BaseModel):
    """Input for measuring the distance between two points."""

    point_a: list[float] = Field(..., description="First point [x, y, (z)]")
    point_b: list[float] = Field(..., description="Second point [x, y, (z)]")


class MeasureDistanceOutput(BaseModel):
    """Output for distance measurement."""

    distance: float = Field(..., description="Distance between the two points")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class MeasureAreaInput(BaseModel):
    """Input for measuring an object's area (or volume)."""

    object_id: str = Field(..., description="Object id to measure")


class MeasureAreaOutput(BaseModel):
    """Output for area/volume measurement."""

    value: float = Field(..., description="Measured value")
    unit: str = Field(..., description="mm^2 for area, mm^3 for volume")
    kind: str = Field(..., description="Measurement kind: area / volume")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


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
        return float(math.pi * params["height"] / 3.0 * (rb**2 + rt**2 + rb * rt))
    raise EntityError(f"No volume defined for {kind}", code="unsupported_measure")


def _area_or_volume(kind: str, params: dict[str, Any]) -> tuple[float, str, str]:
    if kind == "circle":
        return math.pi * params["radius"] ** 2, "mm^2", "area"
    if kind == "rectangle":
        return params["width"] * params["height"], "mm^2", "area"
    if kind == "polygon":
        n = params["sides"]
        value = 0.5 * n * params["radius"] ** 2 * math.sin(2 * math.pi / n)
        return value, "mm^2", "area"
    if kind in ("box", "cylinder", "sphere", "cone"):
        return _solid_volume(kind, params), "mm^3", "volume"
    raise EntityError(f"No area defined for type {kind!r}", code="unsupported_measure")


def cad_measure_distance(input: MeasureDistanceInput) -> MeasureDistanceOutput:
    """Measure the distance between two points.

    测量两点之间的欧氏距离。点可以是 2D [x, y] 或 3D [x, y, z]。
    """
    try:
        if len(input.point_a) < 2 or len(input.point_b) < 2:
            raise EntityError("Each point needs at least two coordinates", code="invalid_point")
        distance = math.dist(input.point_a, input.point_b)
        return MeasureDistanceOutput(distance=distance, status="success")
    except CADError as exc:
        return MeasureDistanceOutput(distance=0.0, status="error", message=str(exc))


def cad_measure_area(input: MeasureAreaInput) -> MeasureAreaOutput:
    """Measure an object's area (2D) or volume (3D).

    测量对象面积（圆/矩形/多边形）或体积（长方体/圆柱/球/圆锥）。
    """
    try:
        doc = DocumentManager().get_current()
        record = doc.entities.get(input.object_id)
        params = record.shape["params"]
        value, unit, kind = _area_or_volume(record.type, params)
        return MeasureAreaOutput(
            value=value,
            unit=unit,
            kind=kind,
            status="success",
            message=f"{kind.title()} of {input.object_id}",
        )
    except CADError as exc:
        return MeasureAreaOutput(
            value=0.0, unit="mm^2", kind="area", status="error", message=str(exc)
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_measure_distance", cad_measure_distance),
    ("cad_measure_area", cad_measure_area),
]
