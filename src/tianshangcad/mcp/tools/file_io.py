"""File export/import tools (DXF / STL / STEP / JSON)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import CADError


class FileExportInput(BaseModel):
    """Input for exporting the current document to a file."""

    format: str = Field(
        ...,
        description=(
            "Export format: step (recommended), dxf, stl, dwg, json"
        ),
        examples=["step"],
    )
    path: str = Field(..., description="Target file path")


class FileExportOutput(BaseModel):
    """Output of a file export."""

    path: str = Field(..., description="Written file path")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class FileImportInput(BaseModel):
    """Input for importing a file as a new document."""

    path: str = Field(..., description="File path to import (.json / .dxf / .step)")


class FileImportOutput(BaseModel):
    """Output of a file import."""

    file_id: str = Field(..., description="New document file id")
    object_count: int = Field(..., description="Number of imported objects")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_file_export(input: FileExportInput) -> FileExportOutput:
    """Export the current document to a file.

    STEP is the recommended interchange format: it is lossless for solid
    geometry, requires no external converter, and round-trips through
    ``cad_file_import``. DXF suits 2D annotation; DWG needs the ODA File
    Converter (see the ``ODAFC_PATH`` hint on error).
    """
    try:
        doc = DocumentManager().get_current()
        from tianshangcad.io.exporters.dwg import DWGExporter
        from tianshangcad.io.exporters.dxf import DXFExporter
        from tianshangcad.io.exporters.json_io import JSONExporter
        from tianshangcad.io.exporters.step import STEPExporter
        from tianshangcad.io.exporters.stl import STLExporter

        fmt = input.format.lower()
        exporters = {
            "dxf": DXFExporter,
            "stl": STLExporter,
            "step": STEPExporter,
            "dwg": DWGExporter,
            "json": JSONExporter,
        }
        exporter_cls = exporters.get(fmt)
        if exporter_cls is None:
            return FileExportOutput(
                path="",
                status="error",
                message=f"Unsupported export format: {input.format}",
            )
        if fmt == "json":
            exporter_cls().export_to_file(doc, input.path)
        else:
            exporter_cls().export_document(doc, input.path)
        return FileExportOutput(path=input.path, status="success", message="Exported")
    except CADError as exc:
        return FileExportOutput(path="", status="error", message=str(exc))


def cad_file_import(input: FileImportInput) -> FileImportOutput:
    """Import a JSON, DXF, STEP or DWG file as a new document."""
    try:
        from pathlib import Path

        from tianshangcad.core.session import SessionManager

        suffix = Path(input.path).suffix.lower()
        if suffix == ".json":
            from tianshangcad.io.importers.json_io import JSONImporter

            scene = JSONImporter().import_from_file(input.path)
            doc = JSONImporter().scene_to_document(scene, Path(input.path))
        elif suffix == ".dxf":
            from tianshangcad.io.importers.dxf import DXFImporter

            doc = DXFImporter().import_file(input.path)
        elif suffix == ".step":
            from tianshangcad.io.importers.step import STEPImporter

            doc = STEPImporter().import_file(input.path)
        elif suffix == ".dwg":
            from tianshangcad.io.importers.dwg import DWGImporter

            doc = DWGImporter().import_file(input.path)
        else:
            return FileImportOutput(
                file_id="",
                object_count=0,
                status="error",
                message=f"Unsupported import format: {suffix}",
            )
        session = SessionManager().current_session
        session.active_files[doc.file_id] = doc
        session.current_file_id = doc.file_id
        return FileImportOutput(
            file_id=doc.file_id,
            object_count=len(doc.entities.list()),
            status="success",
            message="Imported",
        )
    except CADError as exc:
        return FileImportOutput(
            file_id="", object_count=0, status="error", message=str(exc)
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_file_export", cad_file_export),
    ("cad_file_import", cad_file_import),
]
