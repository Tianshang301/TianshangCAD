"""DXF importer based on ezdxf."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ezdxf

from cad_mcp_server.core.document import DocumentState
from cad_mcp_server.utils.errors import CADImportError

_SUPPORTED_ENTITY_TYPES = {"LINE", "CIRCLE", "ARC", "LWPOLYLINE"}


class DXFImporter:
    """Import DXF files into a document."""

    def import_file(self, filepath: str) -> DocumentState:
        """Read a DXF file and build a new document."""
        path = Path(filepath)
        if not path.is_file():
            raise CADImportError(f"File does not exist: {filepath}", code="file_not_found")
        try:
            d = ezdxf.readfile(str(path))  # type: ignore[attr-defined]
        except (ezdxf.DXFStructureError, OSError) as exc:  # type: ignore[attr-defined]
            raise CADImportError(
                f"Failed to read DXF {filepath}: {exc}", code="read_failed"
            ) from exc

        doc = DocumentState(
            file_id=f"file_{path.stem}",
            filename=path.name,
            unit="mm",
            path=path,
        )
        self._import_layers(doc, d)
        msp = d.modelspace()
        imported = 0
        for entity in msp:
            if entity.dxftype() not in _SUPPORTED_ENTITY_TYPES:
                continue
            layer = getattr(entity.dxf, "layer", "0") or "0"
            if self._import_entity(doc, entity, layer):
                imported += 1
        doc.is_dirty = False
        if imported == 0:
            raise CADImportError(
                f"No supported geometry found in {filepath}", code="no_geometry"
            )
        return doc

    @staticmethod
    def _import_layers(doc: DocumentState, d: Any) -> None:
        for layer in d.layers:
            name = layer.dxf.name
            if name in doc.layers.snapshot()["layers"]:
                continue
            doc.layers.create(name=name)

    def _import_entity(self, doc: DocumentState, entity: Any, layer: str) -> bool:
        dxftype = entity.dxftype()
        try:
            if dxftype == "LINE":
                doc.entities.create(
                    "line",
                    {"start": list(entity.dxf.start)[:3], "end": list(entity.dxf.end)[:3]},
                    layer=layer,
                )
            elif dxftype == "CIRCLE":
                doc.entities.create(
                    "circle",
                    {"center": list(entity.dxf.center)[:3], "radius": float(entity.dxf.radius)},
                    layer=layer,
                )
            elif dxftype == "ARC":
                doc.entities.create(
                    "arc",
                    {
                        "center": list(entity.dxf.center)[:3],
                        "radius": float(entity.dxf.radius),
                        "start_angle": float(entity.dxf.start_angle) % 360.0,
                        "end_angle": float(entity.dxf.end_angle) % 360.0,
                    },
                    layer=layer,
                )
            elif dxftype == "LWPOLYLINE":
                points = [(point[0], point[1]) for point in entity.get_points()]
                doc.entities.create(
                    "polyline",
                    {"points": points, "closed": bool(entity.closed)},
                    layer=layer,
                )
            else:
                return False
        except Exception:
            return False
        return True
