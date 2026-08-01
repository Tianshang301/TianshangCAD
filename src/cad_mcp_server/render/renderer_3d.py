"""3D preview rendering engine.

Renders the tessellated mesh of every entity into a shaded 3D PNG preview
using matplotlib's 3D toolkits (headless ``Agg`` backend).
"""

from __future__ import annotations

import io
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # type: ignore[import-untyped]

from cad_mcp_server.core.kernel import CADKernel, get_kernel
from cad_mcp_server.utils.errors import CADValidationError

DPI_MIN = 72
DPI_MAX = 300


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


def render_3d(
    records: Sequence[Any],
    dpi: int = 96,
    output: str | None = None,
    kernel: CADKernel | None = None,
    title: str | None = None,
) -> bytes:
    """Render entities as a shaded 3D PNG preview.

    ``dpi`` must be within ``[72, 300]``. Returns PNG bytes and, when
    ``output`` is given, also writes them to that path.
    """
    if not DPI_MIN <= dpi <= DPI_MAX:
        raise CADValidationError(
            f"dpi must be within [{DPI_MIN}, {DPI_MAX}]", code="invalid_dpi"
        )
    active_kernel = kernel or get_kernel()
    fig = plt.figure(figsize=(7, 6), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_title(title or "3D preview")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

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
