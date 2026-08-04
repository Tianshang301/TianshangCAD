"""Pydantic v2 geometry schema models.

These models validate the JSON interchange format for geometry objects.
Each concrete geometry carries a ``type`` discriminator.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class LineGeometry(BaseModel):
    """Line segment."""

    type: Literal["line"] = "line"
    start: list[float] = Field(..., min_length=2, max_length=3)
    end: list[float] = Field(..., min_length=2, max_length=3)


class CircleGeometry(BaseModel):
    """Circle."""

    type: Literal["circle"] = "circle"
    center: list[float] = Field(..., min_length=2, max_length=3)
    radius: float = Field(..., gt=0)


class ArcGeometry(BaseModel):
    """Circular arc (angles in degrees)."""

    type: Literal["arc"] = "arc"
    center: list[float] = Field(..., min_length=2, max_length=3)
    radius: float = Field(..., gt=0)
    start_angle: float = Field(..., ge=0, lt=360)
    end_angle: float = Field(..., ge=0, le=360)


class RectangleGeometry(BaseModel):
    """Rectangle."""

    type: Literal["rectangle"] = "rectangle"
    origin: list[float] = Field(..., min_length=2, max_length=3)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    rotation: float = Field(0.0, ge=0, lt=360)


class PolygonGeometry(BaseModel):
    """Regular polygon."""

    type: Literal["polygon"] = "polygon"
    center: list[float] = Field(..., min_length=2, max_length=3)
    radius: float = Field(..., gt=0)
    sides: int = Field(..., ge=3, le=100)
    rotation: float = Field(0.0, ge=0, lt=360)


class PolylineGeometry(BaseModel):
    """Polyline."""

    type: Literal["polyline"] = "polyline"
    points: list[list[float]] = Field(..., min_length=2)
    closed: bool = False


class BoxGeometry(BaseModel):
    """Box (optionally rotated via a 3x3 rotation matrix)."""

    type: Literal["box"] = "box"
    origin: list[float] = Field(..., min_length=3, max_length=3)
    dimensions: list[float] = Field(..., min_length=3, max_length=3)
    rotation: list[list[float]] | None = Field(None)


class CylinderGeometry(BaseModel):
    """Cylinder."""

    type: Literal["cylinder"] = "cylinder"
    origin: list[float] = Field(..., min_length=3, max_length=3)
    radius: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    axis: list[float] = Field(default=[0, 0, 1], min_length=3, max_length=3)


class SphereGeometry(BaseModel):
    """Sphere."""

    type: Literal["sphere"] = "sphere"
    center: list[float] = Field(..., min_length=3, max_length=3)
    radius: float = Field(..., gt=0)


class ConeGeometry(BaseModel):
    """Cone or frustum."""

    type: Literal["cone"] = "cone"
    origin: list[float] = Field(..., min_length=3, max_length=3)
    radius_bottom: float = Field(..., ge=0)
    radius_top: float = Field(0.0, ge=0)
    height: float = Field(..., gt=0)


class MeshGeometry(BaseModel):
    """Triangle mesh."""

    type: Literal["mesh"] = "mesh"
    vertices: list[list[float]]
    faces: list[list[int]]
    normals: list[list[float]] | None = None
    uvs: list[list[float]] | None = None


GeometryType = Annotated[
    LineGeometry
    | CircleGeometry
    | ArcGeometry
    | RectangleGeometry
    | PolygonGeometry
    | PolylineGeometry
    | BoxGeometry
    | CylinderGeometry
    | SphereGeometry
    | ConeGeometry
    | MeshGeometry,
    Field(discriminator="type"),
]


class GeometryObject(BaseModel):
    """Unified geometry object model."""

    id: str = Field(..., description="Object unique identifier")
    type: str = Field(..., description="Geometry type")
    layer: str = Field("0", description="Layer name")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Object properties: color, linetype, linewidth, material",
    )
    geometry: GeometryType
    transform: dict[str, list[float]] | None = Field(
        None,
        description="Transformation: {translation, rotation, scale}",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata: name, description, tags, created_by, created_at",
    )
