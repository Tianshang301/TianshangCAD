"""Pydantic v2 3D view schema model.

Defines the JSON interchange format for 3D views: spherical camera poses,
named views, section planes, exploded views and animation timelines.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ProjectionType = Literal["perspective", "orthographic"]
PlaneType = Literal["XY", "YZ", "XZ"]
AnimationMode = Literal["orbit", "turntable"]

NAMED_VIEWS: dict[str, tuple[float, float]] = {
    "iso": (45.0, 35.264),
    "top": (0.0, 90.0),
    "front": (0.0, 0.0),
    "side": (90.0, 0.0),
    "back": (180.0, 0.0),
    "bottom": (0.0, -90.0),
}


def _deg(value: float) -> float:
    """Clamp a spherical angle into the natural range [-180, 180]."""
    result = (value + 180.0) % 360.0 - 180.0
    if abs(result) < 1e-9 or result != -180.0:
        return result
    return 180.0


class CameraPose(BaseModel):
    """A spherical camera pose: the camera orbits ``target``."""

    azimuth: float = Field(0.0, ge=-360.0, le=360.0, description="Azimuth angle in degrees")
    elevation: float = Field(0.0, ge=-360.0, le=360.0, description="Elevation angle in degrees")
    distance: float = Field(10.0, gt=0, description="Camera distance from target")
    target: list[float] = Field(
        default_factory=lambda: [0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description="Look-at target [x, y, z]",
    )
    fov: float = Field(45.0, gt=1, lt=179, description="Vertical field of view in degrees")
    up: list[float] = Field(
        default_factory=lambda: [0.0, 0.0, 1.0],
        min_length=3,
        max_length=3,
        description="Up vector [x, y, z]",
    )

    @field_validator("azimuth", "elevation")
    @classmethod
    def _normalize_angles(cls, value: float) -> float:
        return _deg(value)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict."""
        return self.model_dump()


class SectionPlane(BaseModel):
    """A planar clipping section used for section views."""

    plane: PlaneType = Field(..., description="Section plane: XY / YZ / XZ")
    offset: float = Field(0.0, description="Offset of the plane along its normal")
    show_cut_faces: bool = Field(True, description="Color the cut surface")


class ExplodeSpec(BaseModel):
    """Per-axis explode offsets as a fraction of the model radius."""

    offset_x: float = Field(0.0, ge=0, description="X explode factor")
    offset_y: float = Field(0.0, ge=0, description="Y explode factor")
    offset_z: float = Field(0.0, ge=0, description="Z explode factor")

    def total(self) -> float:
        """Return the total displacement factor."""
        return self.offset_x + self.offset_y + self.offset_z


class AnimationSpec(BaseModel):
    """Orbit animation timeline definition."""

    mode: AnimationMode = Field("orbit", description="Animation mode")
    frames: int = Field(48, ge=2, le=96, description="Number of frames")
    fps: int = Field(10, ge=1, le=30, description="Frames per second")
    total_degrees: float = Field(360.0, gt=0, le=720, description="Total rotation in degrees")
    elevation_degrees: float = Field(0.0, description="Fixed elevation sweep for turntable")


class View3DDefinition(BaseModel):
    """A named 3D view definition."""

    view_id: str = Field(..., description="View unique identifier")
    name: str = Field(..., description="View name (must be unique per document)")
    projection: ProjectionType = Field("perspective", description="Projection type")
    camera: CameraPose = Field(
        default_factory=lambda: CameraPose(azimuth=45.0, elevation=35.264, distance=10.0),
        description="Spherical camera pose",
    )
    viewport: dict[str, int] = Field(
        default_factory=lambda: {"width": 800, "height": 600},
        description="Rendered viewport in pixels",
    )
    clipping: dict[str, float] = Field(
        default_factory=lambda: {"near": 0.01, "far": 10000.0},
        description="Near / far clipping distances",
    )
    section: SectionPlane | None = Field(None, description="Optional section plane")
    explode: ExplodeSpec | None = Field(None, description="Optional explode offsets")
    fit_to_bounds: bool = Field(True, description="Auto-frame the model bounds")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="View metadata: description, tags, created_at",
    )

    @model_validator(mode="after")
    def _validate_viewport(self) -> View3DDefinition:
        if self.viewport.get("width", 0) < 32 or self.viewport.get("height", 0) < 32:
            raise ValueError("viewport width and height must be >= 32")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict."""
        return self.model_dump()


def named_view(name: str, distance: float = 10.0) -> View3DDefinition:
    """Create a ``View3DDefinition`` for a named view.

    Supported names: ``iso``, ``top``, ``front``, ``side``, ``back``,
    ``bottom``. ``distance`` is the camera distance used when
    ``fit_to_bounds`` is not applied.
    """
    key = name.lower()
    if key not in NAMED_VIEWS:
        raise ValueError(f"Unknown named view {name!r}; expected one of {', '.join(NAMED_VIEWS)}")
    azimuth, elevation = NAMED_VIEWS[key]
    return View3DDefinition(
        view_id=key,
        name=key,
        camera=CameraPose(azimuth=azimuth, elevation=elevation, distance=distance),
        metadata={"description": f"Named {key} view"},
    )


def fit_camera_to_bounds(
    bounds: dict[str, list[float]],
    distance_scale: float = 2.5,
) -> CameraPose:
    """Return a camera pose that frames the given bounds."""
    minimum = bounds["min"]
    maximum = bounds["max"]
    centre = [(minimum[i] + maximum[i]) / 2.0 for i in range(3)]
    radius = max(
        math.dist(minimum, maximum) / 2.0,
        0.001,
    )
    return CameraPose(
        azimuth=45.0,
        elevation=35.264,
        distance=radius * distance_scale,
        target=centre,
    )


def camera_origin(camera: CameraPose) -> list[float]:
    """Compute the camera's world-space position from its pose."""
    azimuth = math.radians(camera.azimuth)
    elevation = math.radians(camera.elevation)
    dx = camera.distance * math.cos(elevation) * math.cos(azimuth)
    dy = camera.distance * math.cos(elevation) * math.sin(azimuth)
    dz = camera.distance * math.sin(elevation)
    return [
        camera.target[0] + dx,
        camera.target[1] + dy,
        camera.target[2] + dz,
    ]
