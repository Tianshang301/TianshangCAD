"""Parametric feature tools: sweep, loft, fillet, chamfer and patterns.

Features create new entities from existing ones. Sweep/loft use the OCCT
kernel when available with an analytic fallback (straight sweeps, stacked
cones); fillet/chamfer are exact on the OCCT path and report
``requires_occ`` otherwise; patterns (linear/circular/mirror) work on
every kernel.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import CADError


class FeatureSweepInput(BaseModel):
    """Input for sweeping a profile along a path."""

    profile_id: str = Field(..., description="Id of the profile entity (circle/rectangle)")
    path: list[list[float]] = Field(..., description="Sweep path polyline points [[x,y,z], ...]")
    object_id: str | None = Field(None, description="Optional id for the result entity")
    layer: str = Field("0", description="Target layer")
    properties: dict[str, Any] | None = Field(None, description="Entity properties")


class FeatureSweepOutput(BaseModel):
    """Output for a sweep."""

    object_id: str = Field(..., description="Result entity id")
    bbox: dict[str, list[float]] = Field(..., description="Result bounding box")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class FeatureLoftInput(BaseModel):
    """Input for lofting between stacked profiles."""

    profile_ids: list[str] = Field(..., description="Profile entity ids, bottom to top")
    sections: list[list[float]] | None = Field(
        None, description="Per-profile [x, y, z] placement (defaults to Z stacking)"
    )
    object_id: str | None = Field(None, description="Optional id for the result entity")
    layer: str = Field("0", description="Target layer")
    properties: dict[str, Any] | None = Field(None, description="Entity properties")


class FeatureLoftOutput(BaseModel):
    """Output for a loft."""

    object_id: str = Field(..., description="Result entity id")
    bbox: dict[str, list[float]] = Field(..., description="Result bounding box")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class FeatureFilletInput(BaseModel):
    """Input for filleting an entity's edges."""

    entity_id: str = Field(..., description="Source entity id")
    radius: float = Field(..., description="Fillet radius", gt=0)
    object_id: str | None = Field(None, description="Optional id for the result entity")
    layer: str = Field("0", description="Target layer")
    properties: dict[str, Any] | None = Field(None, description="Entity properties")


class FeatureFilletOutput(BaseModel):
    """Output for a fillet."""

    object_id: str = Field(..., description="Result entity id")
    bbox: dict[str, list[float]] = Field(..., description="Result bounding box")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class FeatureChamferInput(BaseModel):
    """Input for chamfering an entity's edges."""

    entity_id: str = Field(..., description="Source entity id")
    size: float = Field(..., description="Chamfer size", gt=0)
    object_id: str | None = Field(None, description="Optional id for the result entity")
    layer: str = Field("0", description="Target layer")
    properties: dict[str, Any] | None = Field(None, description="Entity properties")


class FeatureChamferOutput(BaseModel):
    """Output for a chamfer."""

    object_id: str = Field(..., description="Result entity id")
    bbox: dict[str, list[float]] = Field(..., description="Result bounding box")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class FeaturePatternLinearInput(BaseModel):
    """Input for a linear pattern."""

    entity_id: str = Field(..., description="Source entity id")
    direction: list[float] = Field(..., description="Pattern direction [x, y, z]")
    count: int = Field(..., description="Total number of instances (incl. original)", ge=1)
    spacing: float = Field(..., description="Spacing between instances", gt=0)
    layer: str = Field("0", description="Target layer")
    properties: dict[str, Any] | None = Field(None, description="Copy properties")


class FeaturePatternLinearOutput(BaseModel):
    """Output for a linear pattern."""

    object_ids: list[str] = Field(..., description="Instance ids, original first")
    count: int = Field(..., description="Number of instances")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class FeaturePatternCircularInput(BaseModel):
    """Input for a circular pattern."""

    entity_id: str = Field(..., description="Source entity id")
    center: list[float] = Field(..., description="Rotation centre [x, y, z]")
    axis: list[float] = Field(..., description="Rotation axis [x, y, z]")
    count: int = Field(..., description="Number of instances (incl. original)", ge=2)
    angle: float = Field(360.0, description="Angular span in degrees", gt=0)
    layer: str = Field("0", description="Target layer")
    properties: dict[str, Any] | None = Field(None, description="Copy properties")


class FeaturePatternCircularOutput(BaseModel):
    """Output for a circular pattern."""

    object_ids: list[str] = Field(..., description="Instance ids, original first")
    count: int = Field(..., description="Number of instances")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class FeaturePatternMirrorInput(BaseModel):
    """Input for a mirror pattern."""

    entity_id: str = Field(..., description="Source entity id")
    plane_point: list[float] = Field(..., description="A point on the mirror plane [x, y, z]")
    plane_normal: list[float] = Field(..., description="Mirror plane normal [x, y, z]")
    layer: str = Field("0", description="Target layer")
    properties: dict[str, Any] | None = Field(None, description="Copy properties")


class FeaturePatternMirrorOutput(BaseModel):
    """Output for a mirror pattern."""

    object_id: str = Field(..., description="Mirrored entity id")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


def _require_features() -> Any:
    return DocumentManager().get_current().features()


def _bbox(entity_id: str) -> dict[str, list[float]]:
    doc = DocumentManager().get_current()
    return doc.entities.get_bbox(entity_id)


def _feature_output(
    object_id: str, output_cls: type[BaseModel]
) -> BaseModel:
    return output_cls(
        object_id=object_id,
        bbox=_bbox(object_id),
        status="success",
        message=f"Created entity {object_id}",
    )


def _pattern_output(
    object_ids: list[str], output_cls: type[BaseModel], label: str
) -> BaseModel:
    return output_cls(
        object_ids=object_ids,
        count=len(object_ids),
        status="success",
        message=f"{label} produced {len(object_ids)} instances",
    )


def cad_feature_sweep(input: FeatureSweepInput) -> FeatureSweepOutput:
    """Sweep a profile along a path.

    Sweeps a circle/rectangle profile entity along a polyline path,
    producing a new entity. The OCCT kernel gives full generality;
    straight analytic sweeps map circle->cylinder and rectangle->box.
    """
    try:
        object_id = _require_features().sweep(
            input.profile_id, input.path, layer=input.layer, properties=input.properties
        )
        return _feature_output(object_id, FeatureSweepOutput)  # type: ignore[return-value]
    except CADError as exc:
        return FeatureSweepOutput(
            object_id="", bbox=_empty_bbox(), status="error", message=str(exc)
        )


def cad_feature_loft(input: FeatureLoftInput) -> FeatureLoftOutput:
    """Loft between stacked profiles.

    Lofts between two or more profile entities. The OCCT kernel supports
    circle/rectangle profiles; the analytic fallback supports two
    concentric circles (represented as a cone). ``profile_ids`` are ordered
    bottom-to-top and ``sections`` place each profile (defaults to Z
    stacking).

    When not to use: for a single profile extruded along a path use
    ``cad_feature_sweep``; loft is only for transitions between two or more
    stacked profiles. On the analytic kernel non-concentric profiles report
    ``requires_occ``.
    """
    try:
        object_id = _require_features().loft(
            input.profile_ids,
            sections=input.sections,
            layer=input.layer,
            properties=input.properties,
        )
        return _feature_output(object_id, FeatureLoftOutput)  # type: ignore[return-value]
    except CADError as exc:
        return FeatureLoftOutput(object_id="", bbox=_empty_bbox(), status="error", message=str(exc))


def cad_feature_fillet(input: FeatureFilletInput) -> FeatureFilletOutput:
    """Fillet an entity's edges.

    Blends all edges of an entity with the given radius. Requires the
    OCCT kernel (`pip install -e '.[occ]'`); the analytic kernel reports
    ``requires_occ``.
    """
    try:
        object_id = _require_features().fillet(
            input.entity_id, input.radius, layer=input.layer, properties=input.properties
        )
        return _feature_output(object_id, FeatureFilletOutput)  # type: ignore[return-value]
    except CADError as exc:
        return FeatureFilletOutput(
            object_id="", bbox=_empty_bbox(), status="error", message=str(exc)
        )


def cad_feature_chamfer(input: FeatureChamferInput) -> FeatureChamferOutput:
    """Chamfer an entity's edges.

    Cuts all edges of an entity with the given size. Requires the OCCT
    kernel (`pip install -e '.[occ]'`); the analytic kernel reports
    ``requires_occ``.
    """
    try:
        object_id = _require_features().chamfer(
            input.entity_id, input.size, layer=input.layer, properties=input.properties
        )
        return _feature_output(object_id, FeatureChamferOutput)  # type: ignore[return-value]
    except CADError as exc:
        return FeatureChamferOutput(
            object_id="", bbox=_empty_bbox(), status="error", message=str(exc)
        )


def cad_feature_pattern_linear(
    input: FeaturePatternLinearInput,
) -> FeaturePatternLinearOutput:
    """Copy an entity in a linear grid.

    Creates ``count`` instances (the original plus ``count - 1`` copies)
    spaced ``spacing`` apart along ``direction``.
    """
    try:
        ids = _require_features().pattern_linear(
            input.entity_id,
            input.direction,
            input.count,
            input.spacing,
            layer=input.layer,
            properties=input.properties,
        )
        return _pattern_output(ids, FeaturePatternLinearOutput, "Linear pattern")  # type: ignore[return-value]
    except CADError as exc:
        return FeaturePatternLinearOutput(object_ids=[], count=0, status="error", message=str(exc))


def cad_feature_pattern_circular(
    input: FeaturePatternCircularInput,
) -> FeaturePatternCircularOutput:
    """Copy an entity in a circular pattern.

    Creates ``count`` instances evenly spaced across ``angle`` degrees
    around ``axis`` through ``center``.
    """
    try:
        ids = _require_features().pattern_circular(
            input.entity_id,
            input.center,
            input.axis,
            input.count,
            angle=input.angle,
            layer=input.layer,
            properties=input.properties,
        )
        return _pattern_output(ids, FeaturePatternCircularOutput, "Circular pattern")  # type: ignore[return-value]
    except CADError as exc:
        return FeaturePatternCircularOutput(
            object_ids=[], count=0, status="error", message=str(exc)
        )


def cad_feature_pattern_mirror(
    input: FeaturePatternMirrorInput,
) -> FeaturePatternMirrorOutput:
    """Mirror an entity across a plane.

    Creates a mirrored copy across the plane defined by ``plane_point``
    and ``plane_normal``.
    """
    try:
        object_id = _require_features().pattern_mirror(
            input.entity_id,
            input.plane_point,
            input.plane_normal,
            layer=input.layer,
            properties=input.properties,
        )
        return FeaturePatternMirrorOutput(
            object_id=object_id, status="success", message=f"Mirrored to {object_id}"
        )
    except CADError as exc:
        return FeaturePatternMirrorOutput(object_id="", status="error", message=str(exc))


def _empty_bbox() -> dict[str, list[float]]:
    """Return a zero bounding box for error outputs."""
    return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_feature_sweep", cad_feature_sweep),
    ("cad_feature_loft", cad_feature_loft),
    ("cad_feature_fillet", cad_feature_fillet),
    ("cad_feature_chamfer", cad_feature_chamfer),
    ("cad_feature_pattern_linear", cad_feature_pattern_linear),
    ("cad_feature_pattern_circular", cad_feature_pattern_circular),
    ("cad_feature_pattern_mirror", cad_feature_pattern_mirror),
]
