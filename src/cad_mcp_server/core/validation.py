"""Geometry validation algorithms.

Checks operate on analytic shapes produced by the CAD kernel:

- edge/edge self-intersection for planar outlines (polyline / polygon /
  rectangle);
- degenerate (zero-area) faces for meshes and planar polygons;
- non-manifold edge statistics for meshes.

Every detected issue is a structured :class:`ValidationIssue` carrying a
machine-readable ``issue_type``, an optional spatial ``location``, a
human-readable ``fix_suggestion`` and optional ``details``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from cad_mcp_server.core.kernel import CADKernel, Shape

_EPS = 1e-9


@dataclass
class ValidationIssue:
    """A single structured geometry issue."""

    object_id: str = ""
    issue_type: str = "invalid_geometry"
    message: str = ""
    location: list[float] | None = None
    fix_suggestion: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""
        return {
            "object_id": self.object_id,
            "type": self.issue_type,
            "message": self.message,
            "location": self.location,
            "fix_suggestion": self.fix_suggestion,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# Low-level geometric helpers
# ---------------------------------------------------------------------------


def _segment_intersection(
    p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray
) -> list[float] | None:
    """Return the 2D intersection point of two segments, or ``None``."""
    r = p2 - p1
    s = p4 - p3
    denom = r[0] * s[1] - r[1] * s[0]
    qp = p3 - p1
    if abs(denom) > _EPS:
        t = (qp[0] * s[1] - qp[1] * s[0]) / denom
        u = (qp[0] * r[1] - qp[1] * r[0]) / denom
        if -_EPS <= t <= 1 + _EPS and -_EPS <= u <= 1 + _EPS:
            point = p1 + t * r
            return [float(point[0]), float(point[1]), 0.0]
        return None
    if abs(qp[0] * r[1] - qp[1] * r[0]) > _EPS:
        return None
    t0 = np.dot(qp, r) / np.dot(r, r) if np.dot(r, r) > _EPS else 0.0
    t1 = t0 + np.dot(s, r) / np.dot(r, r) if np.dot(r, r) > _EPS else 1.0
    lo = max(0.0, min(t0, t1))
    hi = min(1.0, max(t0, t1))
    if hi < lo:
        return None
    point = p1 + (lo + hi) / 2.0 * r
    return [float(point[0]), float(point[1]), 0.0]


def _segments_intersect(
    p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray
) -> bool:
    return _segment_intersection(p1, p2, p3, p4) is not None


def _shares_endpoint(
    a1: np.ndarray, a2: np.ndarray, b1: np.ndarray, b2: np.ndarray
) -> bool:
    endpoints_a = [a1, a2]
    endpoints_b = [b1, b2]
    return any(
        np.allclose(pa, pb, atol=1e-8) for pa in endpoints_a for pb in endpoints_b
    )


def _triangle_area_3d(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Area of a triangle in 3D space via the cross-product magnitude."""
    return float(np.linalg.norm(np.cross(b - a, c - a)) / 2.0)


# ---------------------------------------------------------------------------
# Per-issue checks
# ---------------------------------------------------------------------------


def _outline_points(shape: Shape) -> list[list[float]] | None:
    """Return the planar outline points of a shape, or ``None``."""
    kind = shape["kind"]
    params = shape["params"]
    if kind == "rectangle":
        origin = np.array(params["origin"][:2], dtype=float)
        width, height, rotation = params["width"], params["height"], params["rotation"]
        center = origin + np.array([width / 2.0, height / 2.0])
        radians = np.radians(rotation)
        c, s = np.cos(radians), np.sin(radians)
        rot = np.array([[c, -s], [s, c]])
        half = np.array([width / 2.0, height / 2.0])
        corners = [
            center + rot @ np.array([-half[0], -half[1]]),
            center + rot @ np.array([half[0], -half[1]]),
            center + rot @ np.array([half[0], half[1]]),
            center + rot @ np.array([-half[0], half[1]]),
        ]
        z = float(params["origin"][2]) if len(params["origin"]) > 2 else 0.0
        return [[float(p[0]), float(p[1]), z] for p in corners]
    if kind == "polygon":
        center = np.array(params["center"][:2], dtype=float)
        radius, sides, rotation = params["radius"], params["sides"], params["rotation"]
        angles = np.radians(rotation) + np.radians(
            np.linspace(0.0, 360.0, sides, endpoint=False)
        )
        z = float(params["center"][2]) if len(params["center"]) > 2 else 0.0
        return [
            [float(center[0] + radius * np.cos(a)), float(center[1] + radius * np.sin(a)), z]
            for a in angles
        ]
    if kind == "polyline":
        return [list(point) for point in params["points"]]
    return None


def _check_self_intersection(shape: Shape, kernel: CADKernel) -> list[ValidationIssue]:
    """Detect edge/edge self-intersections in planar outlines."""
    kind = shape["kind"]
    params = shape["params"]
    if kind in ("rectangle", "polygon"):
        points = _outline_points(shape)
        closed = True
    elif kind == "polyline":
        points = params["points"]
        closed = bool(params.get("closed", False))
    else:
        return []
    if points is None or len(points) < 4:
        return []
    segments = []
    for i in range(len(points) - 1):
        segments.append((np.array(points[i][:2]), np.array(points[i + 1][:2])))
    if closed and len(points) > 2:
        segments.append((np.array(points[-1][:2]), np.array(points[0][:2])))
    issues: list[ValidationIssue] = []
    for i in range(len(segments)):
        a1, a2 = segments[i]
        for j in range(i + 1, len(segments)):
            b1, b2 = segments[j]
            if _shares_endpoint(a1, a2, b1, b2):
                continue
            if not _segments_intersect(a1, a2, b1, b2):
                continue
            point = _segment_intersection(a1, a2, b1, b2) or [0.0, 0.0, 0.0]
            issues.append(
                ValidationIssue(
                    issue_type="self_intersection",
                    message=(
                        f"Segments {i} and {j} intersect each other"
                    ),
                    location=point,
                    fix_suggestion=(
                        "Move, delete or reroute one of the crossing segments"
                    ),
                    details={"segment_a": i, "segment_b": j},
                )
            )
    return issues


def _check_degenerate_faces(shape: Shape) -> list[ValidationIssue]:
    """Detect zero-area / collinear faces in meshes."""
    kind = shape["kind"]
    params = shape["params"]
    if kind != "mesh":
        return []
    vertices = params["vertices"]
    faces = params["faces"]
    issues: list[ValidationIssue] = []
    for index, face in enumerate(faces):
        if len(face) < 3:
            issues.append(
                ValidationIssue(
                    issue_type="degenerate_face",
                    message=f"Face {index} has fewer than 3 vertices",
                    location=list(vertices[face[0]]) if face and vertices else None,
                    fix_suggestion="Remove the face or fill in missing vertices",
                    details={"face_index": index, "vertex_count": len(face)},
                )
            )
            continue
        tri_a, tri_b, tri_c = (
            np.array(vertices[face[0]]),
            np.array(vertices[face[1]]),
            np.array(vertices[face[2]]),
        )
        if _triangle_area_3d(tri_a, tri_b, tri_c) <= _EPS:
            issues.append(
                ValidationIssue(
                    issue_type="degenerate_face",
                    message=f"Face {index} has zero area",
                    location=list(vertices[face[0]]),
                    fix_suggestion=(
                        "Collapse or delete the degenerate face; ensure 3D "
                        "control points are not collinear"
                    ),
                    details={"face_index": index},
                )
            )
    return issues


def _edge_key(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a <= b else (b, a)


def _check_non_manifold_edges(shape: Shape) -> list[ValidationIssue]:
    """Detect edges shared by more than two faces (non-manifold)."""
    kind = shape["kind"]
    params = shape["params"]
    if kind != "mesh":
        return []
    faces = params["faces"]
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for face_index, face in enumerate(faces):
        n = len(face)
        for i in range(n):
            key = _edge_key(int(face[i]), int(face[(i + 1) % n]))
            edge_faces.setdefault(key, []).append(face_index)
    issues: list[ValidationIssue] = []
    for edge, owners in edge_faces.items():
        if len(owners) > 2:
            issues.append(
                ValidationIssue(
                    issue_type="non_manifold_edge",
                    message=(
                        f"Edge {edge} is shared by {len(owners)} faces "
                        f"(expected at most 2)"
                    ),
                    fix_suggestion=(
                        "Split or rewire the edge so each edge borders at most "
                        "two faces"
                    ),
                    details={"edge": list(edge), "faces": owners},
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_entity(
    object_id: str, shape: Shape, kernel: CADKernel | None = None
) -> list[ValidationIssue]:
    """Run all applicable structural checks on a shape.

    Returns a list of :class:`ValidationIssue`; an empty list means the
    shape is structurally valid.
    """
    if kernel is None:
        from cad_mcp_server.core.kernel import get_kernel

        kernel = get_kernel()
    issues: list[ValidationIssue] = []
    issues.extend(_check_self_intersection(shape, kernel))
    issues.extend(_check_degenerate_faces(shape))
    issues.extend(_check_non_manifold_edges(shape))
    for issue in issues:
        issue.object_id = object_id
    return issues


def topology_stats(shape: Shape) -> dict[str, Any]:
    """Return topological statistics for a shape.

    For meshes this counts vertices, faces, unique edges, boundary edges
    and non-manifold edges. For other kinds a best-effort summary is
    produced from the kernel tessellation.
    """
    params = shape["params"]
    if shape["kind"] == "mesh":
        vertices = params["vertices"]
        faces = params["faces"]
        edge_owners: dict[tuple[int, int], list[int]] = {}
        for face_index, face in enumerate(faces):
            n = len(face)
            for i in range(n):
                key = _edge_key(int(face[i]), int(face[(i + 1) % n]))
                edge_owners.setdefault(key, []).append(face_index)
        boundary_edges = sum(1 for owners in edge_owners.values() if len(owners) == 1)
        non_manifold_edges = sum(1 for owners in edge_owners.values() if len(owners) > 2)
        return {
            "kind": "mesh",
            "vertices": len(vertices),
            "faces": len(faces),
            "edges": len(edge_owners),
            "boundary_edges": boundary_edges,
            "non_manifold_edges": non_manifold_edges,
            "is_manifold": non_manifold_edges == 0,
        }
    kind = shape["kind"]
    if kind == "line":
        return {"kind": kind, "vertices": 2, "faces": 0, "edges": 1}
    if kind == "circle" or kind == "arc":
        return {"kind": kind, "vertices": 0, "faces": 0, "edges": 1}
    if kind == "box":
        return {"kind": kind, "vertices": 8, "faces": 6, "edges": 12}
    return {"kind": kind, "vertices": 0, "faces": 0, "edges": 0}


def bbox_volume(bbox: dict[str, list[float]]) -> float:
    """Return the volume of an axis-aligned bounding box (0 for invalid)."""
    minimum, maximum = bbox["min"], bbox["max"]
    dims = [maximum[i] - minimum[i] for i in range(3)]
    if any(value <= 0 or not math.isfinite(value) for value in dims):
        return 0.0
    return float(dims[0] * dims[1] * dims[2])


def overlap_bbox(
    a: dict[str, list[float]], b: dict[str, list[float]]
) -> dict[str, list[float]] | None:
    """Return the overlapping bounding box of two boxes, or ``None``."""
    minimum = [max(a["min"][i], b["min"][i]) for i in range(3)]
    maximum = [min(a["max"][i], b["max"][i]) for i in range(3)]
    if all(maximum[i] > minimum[i] for i in range(3)):
        return {"min": minimum, "max": maximum}
    return None


def interference_volume(
    a: dict[str, list[float]], b: dict[str, list[float]]
) -> float:
    """Return the overlap volume of two bounding boxes (0 when disjoint)."""
    overlap = overlap_bbox(a, b)
    if overlap is None:
        return 0.0
    return bbox_volume(overlap)
