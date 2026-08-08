"""Geometry validation and metrics tools."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import CADError

# Kinds that require an external backend (booleans / BREP) are skipped with
# an informational note rather than an error.
_BOOLEAN_REQUIRED = {"boolean_union", "boolean_subtract", "boolean_intersect"}

if TYPE_CHECKING:
    from tianshangcad.core.document import DocumentState
    from tianshangcad.core.entity import EntityRecord


class ValidateGeometryInput(BaseModel):
    """Input for validating geometry."""

    object_ids: list[str] | None = Field(
        None, description="Object ids to validate (all when omitted)"
    )


class GeometryIssue(BaseModel):
    """A single geometry issue."""

    object_id: str = Field(..., description="Object id")
    type: str = Field(
        ...,
        description="Issue type: self_intersection / degenerate_face / "
        "non_manifold_edge / invalid_bbox",
    )
    issue: str = Field(..., description="Issue description")
    location: list[float] | None = Field(None, description="Spatial location of the issue")
    fix_suggestion: str = Field("", description="Suggested remediation")


class ValidateGeometryOutput(BaseModel):
    """Output for geometry validation."""

    valid: bool = Field(..., description="Whether all checked objects are valid")
    checked: int = Field(..., description="Number of objects checked")
    issues: list[GeometryIssue] = Field(default_factory=list, description="Detected issues")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ValidateInterferenceInput(BaseModel):
    """Input for interference detection."""

    object_ids: list[str] | None = Field(None, description="Object ids to check (all when omitted)")


class InterferencePair(BaseModel):
    """A detected interference between two objects."""

    a: str = Field(..., description="First object id")
    b: str = Field(..., description="Second object id")
    overlap: dict[str, list[float]] = Field(..., description="Overlapping box: {min, max}")
    volume: float = Field(0.0, description="Overlap volume in current document units")


class ValidateInterferenceOutput(BaseModel):
    """Output for interference detection."""

    interference_count: int = Field(..., description="Number of interfering pairs")
    pairs: list[InterferencePair] = Field(default_factory=list, description="Interfering pairs")
    total_volume: float = Field(0.0, description="Sum of all overlap volumes")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ValidateTopologyInput(BaseModel):
    """Input for topology validation."""


class TopologySummary(BaseModel):
    """Topological statistics for a single object."""

    object_id: str = Field(..., description="Object id")
    kind: str = Field(..., description="Geometry kind")
    vertices: int = Field(..., description="Vertex count")
    edges: int = Field(..., description="Edge count")
    faces: int = Field(..., description="Face count")
    non_manifold_edges: int = Field(0, description="Edges shared by > 2 faces")
    is_manifold: bool = Field(True, description="Whether the object is 2-manifold")


class ValidateTopologyOutput(BaseModel):
    """Output for topology validation."""

    object_count: int = Field(..., description="Number of objects")
    kinds: dict[str, int] = Field(..., description="Object count by kind")
    summaries: list[TopologySummary] = Field(
        default_factory=list, description="Per-object topology"
    )
    warnings: list[str] = Field(default_factory=list, description="Topology warnings")
    status: str = Field(..., description="Operation status")


class MetricsGetInput(BaseModel):
    """Input for retrieving metrics."""


class MetricsGetOutput(BaseModel):
    """Output for retrieving metrics."""

    files: int = Field(..., description="Open files")
    objects: int = Field(..., description="Total objects")
    layers: int = Field(..., description="Total layers")
    bbox: dict[str, list[float]] = Field(..., description="Document bounding box")
    kinds: dict[str, int] = Field(..., description="Object count by kind")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _finite_and_positive(bbox: dict[str, list[float]]) -> bool:
    minimum, maximum = bbox["min"], bbox["max"]
    if not all(math.isfinite(value) for value in minimum + maximum):
        return False
    return all(maximum[i] >= minimum[i] for i in range(3))


def _bbox_overlap(
    a: dict[str, list[float]], b: dict[str, list[float]]
) -> dict[str, list[float]] | None:
    minimum = [
        max(a["min"][i], b["min"][i]) for i in range(3)
    ]
    maximum = [
        min(a["max"][i], b["max"][i]) for i in range(3)
    ]
    if all(maximum[i] >= minimum[i] for i in range(3)):
        return {"min": minimum, "max": maximum}
    return None


def _entity_issues(
    doc: DocumentState, record: EntityRecord
) -> list[GeometryIssue]:
    """Run structural validation on a single entity."""
    from tianshangcad.core.validation import validate_entity

    found = validate_entity(record.id, record.shape, doc.entities.kernel)
    if found:
        return [
            GeometryIssue(
                object_id=issue.object_id,
                type=issue.issue_type,
                issue=issue.message,
                location=issue.location,
                fix_suggestion=issue.fix_suggestion,
            )
            for issue in found
        ]
    bbox = doc.entities.get_bbox(record.id)
    if not _finite_and_positive(bbox):
        return [
            GeometryIssue(
                object_id=record.id,
                type="invalid_bbox",
                issue=f"Invalid bounding box: {bbox}",
                fix_suggestion="Check for NaN / infinite coordinates in the shape",
            )
        ]
    return []


def cad_validate_geometry(input: ValidateGeometryInput) -> ValidateGeometryOutput:
    """Validate objects for structural integrity and finite bounding boxes.

    Detects self-intersecting outlines, degenerate faces and non-manifold
    edges. Every issue includes a machine-readable ``type``, a ``location``
    and a ``fix_suggestion``.
    """
    try:
        doc = DocumentManager().get_current()
        records = (
            [doc.entities.read(object_id) for object_id in input.object_ids]
            if input.object_ids is not None
            else doc.entities.list()
        )
        issues: list[GeometryIssue] = []
        for record in records:
            issues.extend(_entity_issues(doc, record))
        return ValidateGeometryOutput(
            valid=not issues,
            checked=len(records),
            issues=issues,
            status="success",
            message="OK" if not issues else f"{len(issues)} issue(s) found",
        )
    except CADError as exc:
        return ValidateGeometryOutput(
            valid=False, checked=0, issues=[], status="error", message=str(exc)
        )


def cad_validate_interference(input: ValidateInterferenceInput) -> ValidateInterferenceOutput:
    """Detect axis-aligned bounding box interferences between objects.

    Reports each interfering pair together with the overlap box and the
    overlap volume in current document units.
    """
    try:
        from tianshangcad.core.validation import interference_volume

        doc = DocumentManager().get_current()
        records = (
            [doc.entities.read(object_id) for object_id in input.object_ids]
            if input.object_ids is not None
            else doc.entities.list()
        )
        bboxes = [(record.id, doc.entities.get_bbox(record.id)) for record in records]
        pairs: list[InterferencePair] = []
        total_volume = 0.0
        for i in range(len(bboxes)):
            for j in range(i + 1, len(bboxes)):
                overlap = _bbox_overlap(bboxes[i][1], bboxes[j][1])
                if overlap is None:
                    continue
                volume = interference_volume(bboxes[i][1], bboxes[j][1])
                total_volume += volume
                pairs.append(
                    InterferencePair(
                        a=bboxes[i][0],
                        b=bboxes[j][0],
                        overlap=overlap,
                        volume=volume,
                    )
                )
        return ValidateInterferenceOutput(
            interference_count=len(pairs),
            pairs=pairs,
            total_volume=total_volume,
            status="success",
        )
    except CADError as exc:
        return ValidateInterferenceOutput(
            interference_count=0, pairs=[], total_volume=0.0, status="error", message=str(exc)
        )


def cad_validate_topology(input: ValidateTopologyInput) -> ValidateTopologyOutput:
    """Summarize object topology and detect non-manifold edges."""
    try:
        from tianshangcad.core.validation import topology_stats

        doc = DocumentManager().get_current()
        records = doc.entities.list()
        kinds: dict[str, int] = {}
        summaries: list[TopologySummary] = []
        warnings: list[str] = []
        for record in records:
            kinds[record.type] = kinds.get(record.type, 0) + 1
            stats = topology_stats(record.shape)
            summaries.append(
                TopologySummary(
                    object_id=record.id,
                    kind=record.type,
                    vertices=stats["vertices"],
                    edges=stats["edges"],
                    faces=stats["faces"],
                    non_manifold_edges=stats.get("non_manifold_edges", 0),
                    is_manifold=stats.get("is_manifold", True),
                )
            )
            if stats.get("non_manifold_edges", 0):
                warnings.append(
                    f"{record.id} has {stats['non_manifold_edges']} non-manifold edge(s)"
                )
        return ValidateTopologyOutput(
            object_count=len(records),
            kinds=kinds,
            summaries=summaries,
            warnings=warnings,
            status="success",
        )
    except CADError:
        return ValidateTopologyOutput(
            object_count=0, kinds={}, summaries=[], warnings=[], status="error"
        )


def cad_metrics_get(input: MetricsGetInput) -> MetricsGetOutput:
    """Return document metrics: counts, kind histogram and bounding box."""
    try:
        manager = DocumentManager()
        info = manager.info()
        doc = manager.get_current()
        kinds: dict[str, int] = {}
        for record in doc.entities.list():
            kinds[record.type] = kinds.get(record.type, 0) + 1
        return MetricsGetOutput(
            files=len(manager.list()),
            objects=info["entity_count"],
            layers=info["layer_count"],
            bbox=info["bbox"],
            kinds=kinds,
            status="success",
        )
    except CADError as exc:
        return MetricsGetOutput(
            files=0, objects=0, layers=0,
            bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
            kinds={}, status="error", message=str(exc),
        )


# ---------------------------------------------------------------------------
# Aggregate cad_validate tool
# ---------------------------------------------------------------------------


class ValidateGeometryParams(ValidateGeometryInput):
    """Validate geometry."""

    action: Literal["geometry"] = "geometry"


class ValidateInterferenceParams(ValidateInterferenceInput):
    """Detect interferences."""

    action: Literal["interference"] = "interference"


class ValidateTopologyParams(ValidateTopologyInput):
    """Inspect topology."""

    action: Literal["topology"] = "topology"


class MetricsGetParams(MetricsGetInput):
    """Fetch document metrics."""

    action: Literal["metrics"] = "metrics"


ValidateActionParams = Annotated[
    ValidateGeometryParams
    | ValidateInterferenceParams
    | ValidateTopologyParams
    | MetricsGetParams,
    Field(discriminator="action"),
]


class ValidateInput(BaseModel):
    """Input for the aggregate validation tool.

    聚合校验工具。``action`` 决定操作：geometry / interference / topology / metrics。
    """

    query: ValidateActionParams = Field(
        ...,
        description=(
            "Validation action to perform, discriminated by `action`: geometry, "
            "interference, topology or metrics."
        ),
    )


class ValidateOutput(BaseModel):
    """Output of the aggregate validation tool."""

    action: str = Field(..., description="Validation action executed")
    valid: bool = Field(False, description="Whether all checked objects are valid")
    checked: int = Field(0, description="Number of objects checked")
    issues: list[GeometryIssue] = Field(default_factory=list, description="Detected issues")
    interference_count: int = Field(0, description="Number of interfering pairs")
    pairs: list[InterferencePair] = Field(default_factory=list, description="Interfering pairs")
    total_volume: float = Field(0.0, description="Sum of all overlap volumes")
    object_count: int = Field(0, description="Number of objects")
    kinds: dict[str, int] = Field(default_factory=dict, description="Object count by kind")
    summaries: list[TopologySummary] = Field(
        default_factory=list, description="Per-object topology"
    )
    warnings: list[str] = Field(default_factory=list, description="Topology warnings")
    files: int = Field(0, description="Open files")
    objects: int = Field(0, description="Total objects")
    layers: int = Field(0, description="Total layers")
    bbox: dict[str, list[float]] = Field(
        default_factory=lambda: {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
        description="Document bounding box",
    )
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _validate_result(action: str, result: BaseModel) -> ValidateOutput:
    data = result.model_dump()
    data["action"] = action
    return ValidateOutput(**data)


def cad_validate(input: ValidateInput) -> ValidateOutput:
    """Validate geometry, detect interference, inspect topology or fetch metrics.

    聚合校验操作。按 ``action`` 派发：geometry / interference / topology / metrics。
    - ``geometry``: check objects for self-intersections, degenerate faces and
      non-manifold edges (optional ``object_ids`` filter); returns issues with
      ``type`` / ``location`` / ``fix_suggestion``.
    - ``interference``: detect box-box overlaps between objects, with overlap
      volume per pair.
    - ``topology``: per-object vertex/edge/face counts and manifold status.
    - ``metrics``: aggregate document stats (files, objects, layers, bbox,
      kinds) for the current session.

    When not to use: ``cad_validate`` analyzes correctness and aggregates.
    For simple geometric measurements (distance / area) use ``cad_measure``;
    for live server/file/object status use ``cad_status``; for JSON scene
    validation against the schema use ``cad_json`` (action=validate).
    """
    params = input.query
    if params.action == "geometry":
        return _validate_result("geometry", cad_validate_geometry(params))
    if params.action == "interference":
        return _validate_result("interference", cad_validate_interference(params))
    if params.action == "topology":
        return _validate_result("topology", cad_validate_topology(params))
    if params.action == "metrics":
        return _validate_result("metrics", cad_metrics_get(params))
    return ValidateOutput(action=params.action, status="error", message="Unknown action")


#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_validate", cad_validate),
]
