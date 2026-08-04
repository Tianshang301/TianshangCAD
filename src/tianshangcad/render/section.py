"""Section (planar clipping) rendering helpers.

Clips the tessellated triangle mesh of every entity against a single
axis-aligned plane (XY / YZ / XZ) and returns the triangles kept on the
``keep_side`` plus an optional highlight of the cut surface.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from tianshangcad.core.kernel import CADKernel, get_kernel
from tianshangcad.schemas.view3d import SectionPlane

_EPS = 1e-9

# A point is [x, y, z]; a triangle is three points.
Point3 = list[float]
Triangle = list[Point3]

_PLANE_AXIS: dict[str, int] = {"XY": 2, "YZ": 0, "XZ": 1}


def _clip_triangle_against_axis(
    triangle: Triangle, axis: int, offset: float, keep_positive: bool
) -> list[Triangle]:
    """Clip a triangle against the plane ``coord[axis] == offset``.

    Vertices on the keep side (>= offset when keep_positive) are retained;
    the triangle is re-triangulated into 0-2 output triangles.
    """
    keep = [1 if vertex[axis] >= offset - _EPS else 0 for vertex in triangle]
    if all(keep):
        return [triangle]
    if not any(keep):
        return []
    # Build the polygon of kept vertices + edge intersections in order.
    polygon: list[Point3] = []
    for i in range(3):
        if keep[i]:
            polygon.append(triangle[i])
        a = triangle[i]
        b = triangle[(i + 1) % 3]
        if keep[i] != keep[(i + 1) % 3]:
            t = (offset - a[axis]) / (b[axis] - a[axis])
            intersection: Point3 = [a[j] + t * (b[j] - a[j]) for j in range(3)]
            intersection[axis] = offset
            polygon.append(intersection)
    if len(polygon) < 3:
        return []
    # Simple fan triangulation (polygon is convex for a plane clip).
    return [
        [polygon[0], polygon[k], polygon[k + 1]]
        for k in range(1, len(polygon) - 1)
    ]


def _clip_triangles(
    triangles: list[Triangle],
    plane: SectionPlane,
) -> tuple[list[Triangle], list[list[Point3]]]:
    """Return ``(kept_triangles, cut_faces)`` for the section plane.

    ``kept_triangles`` are the portions on the positive side of the plane;
    ``cut_faces`` are the flat polygons lying exactly on the plane (used to
    highlight the section surface).
    """
    axis = _PLANE_AXIS[plane.plane]
    offset = plane.offset
    kept: list[Triangle] = []
    cut: list[list[Point3]] = []
    for triangle in triangles:
        clipped = _clip_triangle_against_axis(triangle, axis, offset, True)
        kept.extend(clipped)
        # For each clipped triangle, the edge that crossed the plane is part
        # of the cut surface. Collect intersection segments on the plane.
        for candidate in clipped:
            for i in range(3):
                a = candidate[i]
                b = candidate[(i + 1) % 3]
                if a[axis] == offset and b[axis] == offset:
                    cut.append([a, b])
    return kept, cut


def _collect_triangles(
    records: Sequence[Any], kernel: CADKernel
) -> list[Triangle]:
    """Tessellate all records into a flat list of triangles."""
    triangles: list[list[list[float]]] = []
    for record in records:
        shape = record.shape
        kind = shape["kind"]
        if kind in ("line", "circle", "arc"):
            continue
        vertices, faces = kernel.tessellate(shape)
        for face in faces:
            if len(face) < 3:
                continue
            triangles.append(
                [
                    [vertices[face[0]][0], vertices[face[0]][1], vertices[face[0]][2]],
                    [vertices[face[1]][0], vertices[face[1]][1], vertices[face[1]][2]],
                    [vertices[face[2]][0], vertices[face[2]][1], vertices[face[2]][2]],
                ]
            )
    return triangles


def section_mesh(
    records: Sequence[Any],
    plane: SectionPlane,
    kernel: CADKernel | None = None,
) -> tuple[list[Triangle], list[list[Point3]]]:
    """Return ``(kept_triangles, cut_edges)`` after clipping by ``plane``.

    ``cut_edges`` are pairs of points (2-vertex polygons) lying on the
    section plane, suitable for drawing the cut outline.
    """
    active_kernel = kernel or get_kernel()
    triangles = _collect_triangles(records, active_kernel)
    return _clip_triangles(triangles, plane)


def bounds_radius(records: Sequence[Any], kernel: CADKernel | None = None) -> float:
    """Return the radius of the bounding sphere of all records."""
    active_kernel = kernel or get_kernel()
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    for record in records:
        bbox = active_kernel.get_bbox(record.shape)
        for i in range(3):
            minimum[i] = min(minimum[i], bbox["min"][i])
            maximum[i] = max(maximum[i], bbox["max"][i])
    if any(value == float("inf") for value in minimum):
        return 1.0
    import math

    radius = math.dist(minimum, maximum) / 2.0
    return radius if radius > 0 else 1.0
