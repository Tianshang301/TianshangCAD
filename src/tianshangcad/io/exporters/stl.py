"""Binary STL exporter."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import numpy as np

from tianshangcad.core.document import DocumentState
from tianshangcad.core.kernel import AnalyticKernel
from tianshangcad.utils.errors import CADExportError, CADNotImplementedError

_NdArray = np.ndarray[Any, Any]


class STLExporter:
    """Export solid entities to a binary STL file."""

    def __init__(self, kernel: AnalyticKernel | None = None) -> None:
        """Initialize with an analytic kernel (or create a default one)."""
        self._kernel = kernel or AnalyticKernel()

    def export_document(self, doc: DocumentState, filepath: str, deflection: float = 0.1) -> None:
        """Write ``doc``'s solid entities to a binary STL file."""
        triangles: list[tuple[_NdArray, _NdArray, _NdArray]] = []
        for record in doc.entities.list():
            try:
                vertices, faces = self._kernel.tessellate(record.shape, deflection)
            except CADNotImplementedError:
                continue
            if len(vertices) < 3:
                continue
            for face in faces:
                if len(face) < 3:
                    continue
                triangles.append(
                    (
                        np.array(vertices[face[0]], dtype=float),
                        np.array(vertices[face[1]], dtype=float),
                        np.array(vertices[face[2]], dtype=float),
                    )
                )
        if not triangles:
            raise CADExportError(
                "No solid geometry to export to STL", code="no_solid_geometry"
            )
        self._write_binary(Path(filepath), triangles)

    @staticmethod
    def _write_binary(
        path: Path, triangles: list[tuple[_NdArray, _NdArray, _NdArray]]
    ) -> None:
        try:
            with path.open("wb") as handle:
                handle.write(b"binary stl export".ljust(80, b"\x00"))
                handle.write(struct.pack("<I", len(triangles)))
                for a, b, c in triangles:
                    normal = _triangle_normal(a, b, c)
                    handle.write(struct.pack("<3f", *normal))
                    for vertex in (a, b, c):
                        handle.write(struct.pack("<3f", *vertex))
                    handle.write(struct.pack("<H", 0))
        except OSError as exc:
            raise CADExportError(
                f"Failed to write STL {path}: {exc}", code="write_failed"
            ) from exc


def _triangle_normal(a: _NdArray, b: _NdArray, c: _NdArray) -> _NdArray:
    u = b - a
    v = c - a
    normal = np.cross(u, v)
    length = np.linalg.norm(normal)
    if length == 0:
        return np.zeros(3)
    return normal / length  # type: ignore[no-any-return]
