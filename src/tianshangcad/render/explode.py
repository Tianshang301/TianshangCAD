"""Exploded view rendering helpers.

Translates the tessellated vertices of every entity away from the model
centre along each axis by a fraction of the model radius, producing a
spatially separated exploded view.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from tianshangcad.core.kernel import CADKernel, get_kernel
from tianshangcad.render.section import bounds_radius
from tianshangcad.schemas.view3d import ExplodeSpec


def explode_mesh(
    records: Sequence[Any],
    spec: ExplodeSpec,
    kernel: CADKernel | None = None,
) -> list[list[list[float]]]:
    """Return the tessellated triangles of ``records`` in exploded layout.

    Each entity is displaced outward from the model centre by
    ``offset_axis * radius * sign(centre_delta)`` per axis.
    """
    active_kernel = kernel or get_kernel()
    radius = bounds_radius(records, active_kernel)
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    for record in records:
        bbox = active_kernel.get_bbox(record.shape)
        for i in range(3):
            minimum[i] = min(minimum[i], bbox["min"][i])
            maximum[i] = max(maximum[i], bbox["max"][i])
    centre = [
        (minimum[i] + maximum[i]) / 2.0 if minimum[i] != float("inf") else 0.0
        for i in range(3)
    ]
    offsets = [spec.offset_x, spec.offset_y, spec.offset_z]

    triangles: list[list[list[float]]] = []
    for record in records:
        shape = record.shape
        kind = shape["kind"]
        if kind in ("line", "circle", "arc"):
            continue
        vertices, faces = active_kernel.tessellate(shape)
        bbox = active_kernel.get_bbox(shape)
        entity_centre = [
            (bbox["min"][i] + bbox["max"][i]) / 2.0 for i in range(3)
        ]
        displacement = [
            offsets[axis] * radius * (1.0 if entity_centre[axis] >= centre[axis] else -1.0)
            for axis in range(3)
        ]
        for face in faces:
            if len(face) < 3:
                continue
            triangle = [
                [
                    vertices[face[0]][0] + displacement[0],
                    vertices[face[0]][1] + displacement[1],
                    vertices[face[0]][2] + displacement[2],
                ],
                [
                    vertices[face[1]][0] + displacement[0],
                    vertices[face[1]][1] + displacement[1],
                    vertices[face[1]][2] + displacement[2],
                ],
                [
                    vertices[face[2]][0] + displacement[0],
                    vertices[face[2]][1] + displacement[1],
                    vertices[face[2]][2] + displacement[2],
                ],
            ]
            triangles.append(triangle)
    return triangles
