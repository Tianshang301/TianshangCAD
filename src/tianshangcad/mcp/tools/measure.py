"""Measurement MCP tools: distance, area and volume."""

from __future__ import annotations

import math
from typing import Annotated, Any, Literal

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
# Aggregate cad_measure tool
# ---------------------------------------------------------------------------


class MeasureDistanceParams(MeasureDistanceInput):
    """Measure the distance between two points."""

    action: Literal["distance"] = "distance"


class MeasureAreaParams(MeasureAreaInput):
    """Measure an object's area (or volume)."""

    action: Literal["area"] = "area"


MeasureActionParams = Annotated[
    MeasureDistanceParams | MeasureAreaParams,
    Field(discriminator="action"),
]


class MeasureInput(BaseModel):
    """Input for the aggregate measurement tool.

    聚合测量工具。``action`` 决定操作：distance / area。
    """

    measure: MeasureActionParams = Field(
        ...,
        description=(
            "Measurement to perform, discriminated by `action`: distance or area."
        ),
    )


class MeasureOutput(BaseModel):
    """Output of the aggregate measurement tool."""

    action: str = Field(..., description="Measurement action executed")
    distance: float = Field(0.0, description="Distance between the two points")
    value: float = Field(0.0, description="Measured value")
    unit: str = Field("", description="mm^2 for area, mm^3 for volume")
    kind: str = Field("", description="Measurement kind: area / volume")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _measure_result(action: str, result: BaseModel) -> MeasureOutput:
    data = result.model_dump()
    data["action"] = action
    return MeasureOutput(**data)


def cad_measure(input: MeasureInput) -> MeasureOutput:
    """Measure a distance or an object's area/volume.

    聚合测量操作。按 ``action`` 派发：distance / area。
    - ``distance``: Euclidean distance between ``point_a`` and ``point_b``
      (2D ``[x, y]`` or 3D ``[x, y, z]``), returns ``distance``.
    - ``area``: measure an existing object by ``object_id`` — 2D kinds
      (circle / rectangle / polygon) return area (``mm^2``), 3D kinds
      (box / cylinder / sphere / cone) return volume (``mm^3``); ``kind``
      in the output reports which.

    When not to use: ``cad_measure`` reads existing geometry. To query
    object position / bounding box use ``cad_object`` (action=read) or
    ``cad_status`` (target=object); to validate mesh validity use
    ``cad_validate`` (action=geometry).
    """
    params = input.measure
    if params.action == "distance":
        return _measure_result("distance", cad_measure_distance(params))
    if params.action == "area":
        return _measure_result("area", cad_measure_area(params))
    return MeasureOutput(action=params.action, status="error", message="Unknown action")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_measure", cad_measure),
]
