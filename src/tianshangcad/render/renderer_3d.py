"""3D preview rendering engine.

Renders the tessellated mesh of every entity into a shaded 3D PNG preview
using matplotlib's 3D toolkits (headless ``Agg`` backend).
"""

from __future__ import annotations

import contextlib
import io
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # type: ignore[import-untyped]

from tianshangcad.core.kernel import CADKernel, get_kernel
from tianshangcad.schemas.view3d import CameraPose
from tianshangcad.utils.errors import CADValidationError

DPI_MIN = 72
DPI_MAX = 300

VALID_PROJECTIONS = ("perspective", "orthographic")


def _tessellated_faces(
    shape: dict[str, Any], kernel: CADKernel
) -> list[list[tuple[float, float, float]]]:
    """Return triangle polygons for a shape's surface mesh."""
    vertices, faces = kernel.tessellate(shape)
    return [
        [
            (vertices[face[0]][0], vertices[face[0]][1], vertices[face[0]][2]),
            (vertices[face[1]][0], vertices[face[1]][1], vertices[face[1]][2]),
            (vertices[face[2]][0], vertices[face[2]][1], vertices[face[2]][2]),
        ]
        for face in faces
        if len(face) >= 3
    ]


def _camera_to_view_init(
    camera: CameraPose, ax: Any, projection: str = "perspective"
) -> tuple[float, float]:
    """Apply a camera pose to a matplotlib 3D axis.

    Returns the ``(elevation, azimuth)`` passed to ``ax.view_init``. The
    camera distance is applied to the axis ``dist``.
    """
    elevation = camera.elevation
    azimuth = camera.azimuth
    ax.set_proj_type("persp" if projection == "perspective" else "ortho")
    ax.view_init(elev=elevation, azim=azimuth)
    # matplotlib flips the sign of the azimuth internally; apply the
    # camera distance through the view distance property when available.
    dist = getattr(ax, "dist", None)
    if dist is not None:
        with contextlib.suppress(AttributeError):
            ax.dist = float(camera.distance)
    return elevation, azimuth


def _apply_camera(
    ax: Any, camera: CameraPose | None, projection: str = "perspective"
) -> None:
    """Configure a 3D axis from an optional camera pose."""
    if camera is None:
        return
    ax.set_xlim3d(
        camera.target[0] - camera.distance,
        camera.target[0] + camera.distance,
    )
    ax.set_ylim3d(
        camera.target[1] - camera.distance,
        camera.target[1] + camera.distance,
    )
    ax.set_zlim3d(
        camera.target[2] - camera.distance,
        camera.target[2] + camera.distance,
    )
    _camera_to_view_init(camera, ax, projection)


def render_3d_triangles(
    triangles: Sequence[Sequence[Sequence[float]]],
    dpi: int = 96,
    output: str | None = None,
    title: str | None = None,
    camera: CameraPose | None = None,
    projection: str = "perspective",
    extra_polygons: Sequence[Any] | None = None,
    cut_edges: Sequence[Sequence[Sequence[float]]] | None = None,
) -> bytes:
    """Render an explicit triangle list as a shaded 3D PNG.

    ``triangles`` are ``[ [ [x,y,z]x3 ] ]`` polygons. ``extra_polygons``
    and ``cut_edges`` are optional additional 3D collections (e.g. section
    cut surface or outline) drawn on top.
    """
    if not DPI_MIN <= dpi <= DPI_MAX:
        raise CADValidationError(
            f"dpi must be within [{DPI_MIN}, {DPI_MAX}]", code="invalid_dpi"
        )
    if projection not in VALID_PROJECTIONS:
        raise CADValidationError(
            f"projection must be one of {', '.join(VALID_PROJECTIONS)}",
            code="invalid_projection",
        )
    fig = plt.figure(figsize=(7, 6), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_title(title or "3D preview")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    _apply_camera(ax, camera, projection)

    polygons = [
        [tuple(vertex) for vertex in triangle]
        for triangle in triangles
        if len(triangle) >= 3
    ]
    if polygons:
        collection = Poly3DCollection(polygons, alpha=0.7, facecolor="cornflowerblue")
        collection.set_edgecolor("black")
        ax.add_collection3d(collection)
    for extra in extra_polygons or []:
        ax.add_collection3d(extra)
    if cut_edges:
        from mpl_toolkits.mplot3d.art3d import Line3DCollection

        segments = [
            [(edge[0][0], edge[0][1], edge[0][2]), (edge[1][0], edge[1][1], edge[1][2])]
            for edge in cut_edges
            if len(edge) >= 2
        ]
        if segments:
            lines = Line3DCollection(segments, colors="red", linewidths=1.5)
            ax.add_collection3d(lines)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    plt.close(fig)
    png_bytes = buffer.getvalue()
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(png_bytes)
    return png_bytes


def render_3d(
    records: Sequence[Any],
    dpi: int = 96,
    output: str | None = None,
    kernel: CADKernel | None = None,
    title: str | None = None,
    camera: CameraPose | None = None,
    projection: str = "perspective",
) -> bytes:
    """Render entities as a shaded 3D PNG preview.

    ``dpi`` must be within ``[72, 300]``. ``camera`` optionally overrides
    the default viewing angle and distance; ``projection`` selects
    ``perspective`` or ``orthographic``. Returns PNG bytes and, when
    ``output`` is given, also writes them to that path.
    """
    if not DPI_MIN <= dpi <= DPI_MAX:
        raise CADValidationError(
            f"dpi must be within [{DPI_MIN}, {DPI_MAX}]", code="invalid_dpi"
        )
    if projection not in VALID_PROJECTIONS:
        raise CADValidationError(
            f"projection must be one of {', '.join(VALID_PROJECTIONS)}",
            code="invalid_projection",
        )
    active_kernel = kernel or get_kernel()
    fig = plt.figure(figsize=(7, 6), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_title(title or "3D preview")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")
    _apply_camera(ax, camera, projection)

    polygons: list[list[tuple[float, float, float]]] = []
    for record in records:
        shape = record.shape
        kind = shape["kind"]
        if kind == "line":
            params = shape["params"]
            ax.plot(
                [params["start"][0], params["end"][0]],
                [params["start"][1], params["end"][1]],
                [params["start"][2], params["end"][2]],
                color="black",
            )
            continue
        if kind in ("circle", "arc"):
            params = shape["params"]
            center = params["center"]
            radius = params["radius"]
            thetas = [i / 36.0 * 2.0 * math.pi for i in range(37)]
            xs = [center[0] + radius * math.cos(theta) for theta in thetas]
            ys = [center[1] + radius * math.sin(theta) for theta in thetas]
            zs = [center[2] for _ in thetas]
            ax.plot(xs, ys, zs, color="black")
            continue
        polygons.extend(_tessellated_faces(shape, active_kernel))

    if polygons:
        collection = Poly3DCollection(polygons, alpha=0.7, facecolor="cornflowerblue")
        collection.set_edgecolor("black")
        ax.add_collection3d(collection)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    plt.close(fig)
    png_bytes = buffer.getvalue()
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(png_bytes)
    return png_bytes
