"""DXF exporter based on ezdxf."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import ezdxf

from cad_mcp_server.core.document import DocumentState
from cad_mcp_server.core.entity import EntityRecord
from cad_mcp_server.core.kernel import CADKernel, get_kernel
from cad_mcp_server.utils.errors import CADExportError

_EZDXF_FORMAT = "R2010"


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


class DXFExporter:
    """Export entities to a DXF file."""

    def __init__(self, kernel: CADKernel | None = None) -> None:
        """Initialize the exporter with an optional geometry kernel."""
        self._kernel = kernel or get_kernel()

    def export_document(self, doc: DocumentState, filepath: str) -> None:
        """Write ``doc`` to a DXF file."""
        d = ezdxf.new(_EZDXF_FORMAT)  # type: ignore[attr-defined]
        for layer in doc.layers.list():
            if layer.name in d.layers:
                continue
            new_layer = d.layers.add(layer.name, linetype=layer.linetype)
            new_layer.rgb = _hex_to_rgb(layer.color)
        msp = d.modelspace()
        exported = 0
        for record in doc.entities.list():
            if self._add_entity(msp, record):
                exported += 1
        try:
            d.saveas(filepath)
        except OSError as exc:
            raise CADExportError(
                f"Failed to write DXF {filepath}: {exc}", code="write_failed"
            ) from exc

    def export_geometry(self, records: Iterable[EntityRecord], filepath: str) -> None:
        """Write a list of entity records to a DXF file."""
        d = ezdxf.new(_EZDXF_FORMAT)  # type: ignore[attr-defined]
        msp = d.modelspace()
        for record in records:
            self._add_entity(msp, record)
        try:
            d.saveas(filepath)
        except OSError as exc:
            raise CADExportError(
                f"Failed to write DXF {filepath}: {exc}", code="write_failed"
            ) from exc

    def _add_entity(self, msp: Any, record: EntityRecord) -> bool:
        kind = record.shape["kind"]
        params = record.shape["params"]
        attribs = {"layer": record.layer}
        if kind == "line":
            msp.add_line(params["start"], params["end"], dxfattribs=attribs)
        elif kind == "circle":
            msp.add_circle(params["center"], params["radius"], dxfattribs=attribs)
        elif kind == "arc":
            msp.add_arc(
                params["center"],
                params["radius"],
                params["start_angle"],
                params["end_angle"],
                dxfattribs=attribs,
            )
        elif kind in ("rectangle", "polygon", "polyline"):
            points = self._outline(record)
            closed = bool(params.get("closed", False)) or kind in ("rectangle", "polygon")
            msp.add_lwpolyline(points, close=closed, dxfattribs=attribs)
        elif kind in ("box", "sphere", "cylinder", "cone", "mesh"):
            self._add_solid_faces(msp, record, attribs)
        else:
            return False
        return True

    def _add_solid_faces(self, msp: Any, record: EntityRecord, attribs: dict[str, Any]) -> None:
        """Tessellate a solid entity and write its triangles as 3DFACE."""
        vertices, faces = self._kernel.tessellate(record.shape)
        for face in faces:
            if len(face) < 3:
                continue
            corners = [
                self._as_point(vertices[vertex_index]) for vertex_index in face[:3]
            ]
            msp.add_3dface(corners, dxfattribs=attribs)

    @staticmethod
    def _as_point(vertex: Sequence[float]) -> tuple[float, float, float]:
        """Normalize a vertex to a 3D point."""
        return (
            float(vertex[0]),
            float(vertex[1]),
            float(vertex[2]) if len(vertex) > 2 else 0.0,
        )

    @staticmethod
    def _outline(record: EntityRecord) -> list[tuple[float, float]]:
        from cad_mcp_server.core.kernel import AnalyticKernel

        kernel = AnalyticKernel()
        points = kernel.outline_points(record.shape)
        return [(point[0], point[1]) for point in points]
