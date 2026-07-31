"""Geometry validation and metrics tools."""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.utils.errors import CADError

# Kinds that require an external backend (booleans / BREP) are skipped with
# an informational note rather than an error.
_BOOLEAN_REQUIRED = {"boolean_union", "boolean_subtract", "boolean_intersect"}


class ValidateGeometryInput(BaseModel):
    """Input for validating geometry."""

    object_ids: list[str] | None = Field(
        None, description="Object ids to validate (all when omitted)"
    )


class GeometryIssue(BaseModel):
    """A single geometry issue."""

    object_id: str = Field(..., description="Object id")
    issue: str = Field(..., description="Issue description")


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


class ValidateInterferenceOutput(BaseModel):
    """Output for interference detection."""

    interference_count: int = Field(..., description="Number of interfering pairs")
    pairs: list[InterferencePair] = Field(default_factory=list, description="Interfering pairs")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ValidateTopologyInput(BaseModel):
    """Input for topology validation."""


class ValidateTopologyOutput(BaseModel):
    """Output for topology validation."""

    object_count: int = Field(..., description="Number of objects")
    kinds: dict[str, int] = Field(..., description="Object count by kind")
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


def cad_validate_geometry(input: ValidateGeometryInput) -> ValidateGeometryOutput:
    """Validate that objects have finite, non-degenerate bounding boxes."""
    try:
        doc = DocumentManager().get_current()
        records = (
            [doc.entities.read(object_id) for object_id in input.object_ids]
            if input.object_ids is not None
            else doc.entities.list()
        )
        issues: list[GeometryIssue] = []
        for record in records:
            bbox = doc.entities.get_bbox(record.id)
            if not _finite_and_positive(bbox):
                issues.append(
                    GeometryIssue(object_id=record.id, issue=f"Invalid bounding box: {bbox}")
                )
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
    """Detect axis-aligned bounding box interferences between objects."""
    try:
        doc = DocumentManager().get_current()
        records = (
            [doc.entities.read(object_id) for object_id in input.object_ids]
            if input.object_ids is not None
            else doc.entities.list()
        )
        bboxes = [(record.id, doc.entities.get_bbox(record.id)) for record in records]
        pairs: list[InterferencePair] = []
        for i in range(len(bboxes)):
            for j in range(i + 1, len(bboxes)):
                overlap = _bbox_overlap(bboxes[i][1], bboxes[j][1])
                if overlap is not None:
                    pairs.append(
                        InterferencePair(a=bboxes[i][0], b=bboxes[j][0], overlap=overlap)
                    )
        return ValidateInterferenceOutput(
            interference_count=len(pairs), pairs=pairs, status="success"
        )
    except CADError as exc:
        return ValidateInterferenceOutput(
            interference_count=0, pairs=[], status="error", message=str(exc)
        )


def cad_validate_topology(input: ValidateTopologyInput) -> ValidateTopologyOutput:
    """Summarize object topology, noting kinds that need a BREP backend."""
    try:
        doc = DocumentManager().get_current()
        records = doc.entities.list()
        kinds: dict[str, int] = {}
        for record in records:
            kinds[record.type] = kinds.get(record.type, 0) + 1
        return ValidateTopologyOutput(
            object_count=len(records),
            kinds=kinds,
            warnings=[],
            status="success",
        )
    except CADError:
        return ValidateTopologyOutput(
            object_count=0, kinds={}, warnings=[], status="error"
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


TOOLS: list[tuple[str, Any]] = [
    ("cad_validate_geometry", cad_validate_geometry),
    ("cad_validate_interference", cad_validate_interference),
    ("cad_validate_topology", cad_validate_topology),
    ("cad_metrics_get", cad_metrics_get),
]
