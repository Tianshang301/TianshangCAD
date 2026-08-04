"""2D orthographic rendering engine.

Produces PNG images of the active document from the ``top``, ``front`` or
``side`` orthographic view. Uses matplotlib with the non-interactive
``Agg`` backend so rendering works headless.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import Circle

from tianshangcad.core.kernel import CADKernel, Shape, get_kernel
from tianshangcad.utils.errors import CADValidationError

VALID_VIEWS = ("top", "front", "side")
DPI_MIN = 72
DPI_MAX = 300


def project_point(point: Sequence[float], view: str) -> tuple[float, float]:
    """Project a 3D point into a 2D orthographic view plane."""
    x, y, z = point[0], point[1], point[2]
    if view == "top":
        return (float(x), float(y))
    if view == "front":
        return (float(x), float(z))
    if view == "side":
        return (float(y), float(z))
    raise CADValidationError(
        f"Unknown view {view!r}; expected one of {', '.join(VALID_VIEWS)}",
        code="invalid_view",
    )


def _shape_edges(shape: Shape, kernel: CADKernel) -> list[tuple[tuple[float, ...], ...]]:
    """Return the 3D wireframe edges of a shape."""
    kind = shape["kind"]
    params = shape["params"]
    if kind == "line":
        start, end = params["start"], params["end"]
        return [(tuple(start), tuple(end))]
    if kind in ("circle", "arc"):
        return []
    vertices, faces = kernel.tessellate(shape)
    edges: list[tuple[tuple[float, ...], ...]] = []
    seen: set[tuple[int, int]] = set()
    for face in faces:
        n = len(face)
        for i in range(n):
            a, b = face[i], face[(i + 1) % n]
            key = (a, b) if a <= b else (b, a)
            if key in seen:
                continue
            seen.add(key)
            edges.append((tuple(vertices[a]), tuple(vertices[b])))
    return edges


def _collect_2d(
    records: Sequence[Any], view: str, kernel: CADKernel
) -> tuple[list[list[tuple[float, float]]], list[tuple[tuple[float, float], float]]]:
    """Project entities into a flat list of polylines and circles."""
    polylines: list[list[tuple[float, float]]] = []
    circles: list[tuple[tuple[float, float], float]] = []
    for record in records:
        shape = record.shape
        for edge in _shape_edges(shape, kernel):
            a = project_point(edge[0], view)
            b = project_point(edge[1], view)
            polylines.append([a, b])
        kind = shape["kind"]
        if kind == "circle" or kind == "arc":
            params = shape["params"]
            center = project_point(params["center"], view)
            circles.append((center, float(params["radius"])))
    return polylines, circles


def render_view(
    records: Sequence[Any],
    view: str = "top",
    dpi: int = 96,
    output: str | None = None,
    kernel: CADKernel | None = None,
    title: str | None = None,
) -> bytes:
    """Render entities to a PNG in the given orthographic view.

    ``view`` must be one of ``top`` / ``front`` / ``side``. ``dpi`` must be
    within ``[72, 300]``. Returns PNG bytes and, when ``output`` is given,
    also writes them to that path.
    """
    if view not in VALID_VIEWS:
        raise CADValidationError(
            f"Unknown view {view!r}; expected one of {', '.join(VALID_VIEWS)}",
            code="invalid_view",
        )
    if not DPI_MIN <= dpi <= DPI_MAX:
        raise CADValidationError(
            f"dpi must be within [{DPI_MIN}, {DPI_MAX}]", code="invalid_dpi"
        )
    active_kernel = kernel or get_kernel()
    polylines, circles = _collect_2d(records, view, active_kernel)

    fig, ax = plt.subplots(figsize=(6, 6), dpi=dpi)
    ax.set_aspect("equal")
    ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.5)
    ax.set_title(title or f"{view.capitalize()} view")
    for polyline in polylines:
        xs = [point[0] for point in polyline]
        ys = [point[1] for point in polyline]
        ax.plot(xs, ys, color="black", linewidth=1.0)
    for (cx, cy), radius in circles:
        circle = Circle((cx, cy), radius, fill=False, color="black", linewidth=1.0)
        ax.add_patch(circle)

    all_points = [point for polyline in polylines for point in polyline]
    all_points.extend([(cx - r, cy - r) for (cx, cy), r in circles])
    all_points.extend([(cx + r, cy + r) for (cx, cy), r in circles])
    if all_points:
        xs = [point[0] for point in all_points]
        ys = [point[1] for point in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        pad_x = (max_x - min_x) * 0.05 or 1.0
        pad_y = (max_y - min_y) * 0.05 or 1.0
        ax.set_xlim(min_x - pad_x, max_x + pad_x)
        ax.set_ylim(min_y - pad_y, max_y + pad_y)
    else:
        ax.set_xlim(-1, 1)
        ax.set_ylim(-1, 1)

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    plt.close(fig)
    png_bytes = buffer.getvalue()
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(png_bytes)
    return png_bytes
