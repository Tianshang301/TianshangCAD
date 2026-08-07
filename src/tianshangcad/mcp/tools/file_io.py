"""File export/import tools (DXF / STL / STEP / JSON).

The public surface is the single aggregate ``cad_file_io`` tool. The legacy
``cad_file_export`` / ``cad_file_import`` functions remain importable but are
no longer registered.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

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
    """Export the current document to a file."""
    # Deprecated, merged into cad_file_io (action=export)
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
    # Deprecated, merged into cad_file_io (action=import)
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
# Aggregate cad_file_io tool
# ---------------------------------------------------------------------------


class FileExportParams(BaseModel):
    """Export the current document to a file."""

    action: Literal["export"] = "export"
    format: str = Field(
        ...,
        description=(
            "Export format: step (recommended), dxf, stl, dwg, json"
        ),
        examples=["step"],
    )
    path: str = Field(..., description="Target file path")


class FileImportParams(BaseModel):
    """Import a file as a new document."""

    action: Literal["import"] = "import"
    path: str = Field(..., description="File path to import (.json / .dxf / .step)")


FileIoActionParams = Annotated[FileExportParams | FileImportParams, Field(discriminator="action")]


class FileIoInput(BaseModel):
    """Input for the aggregate file IO tool.

    聚合文件导入导出工具。``action`` 为 ``export``（导出当前文档到文件，
    format: step/dxf/stl/dwg/json）或 ``import``（导入文件为新文档）。
    """

    file: FileIoActionParams = Field(
        ...,
        description=(
            "File IO action, discriminated by `action`: export the current "
            "document (step/dxf/stl/dwg/json) or import a file as a new "
            "document."
        ),
    )


class FileIoOutput(BaseModel):
    """Output of the aggregate file IO tool."""

    action: str = Field(..., description="File IO action")
    path: str = Field("", description="Written or imported file path")
    file_id: str = Field("", description="Imported document file id")
    object_count: int = Field(0, description="Number of imported objects")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _do_export(params: FileExportParams) -> tuple[str, str | None]:
    """Export the current document; returns (path, error|None)."""
    doc = DocumentManager().get_current()
    from tianshangcad.io.exporters.dwg import DWGExporter
    from tianshangcad.io.exporters.dxf import DXFExporter
    from tianshangcad.io.exporters.json_io import JSONExporter
    from tianshangcad.io.exporters.step import STEPExporter
    from tianshangcad.io.exporters.stl import STLExporter

    fmt = params.format.lower()
    exporters = {
        "dxf": DXFExporter,
        "stl": STLExporter,
        "step": STEPExporter,
        "dwg": DWGExporter,
        "json": JSONExporter,
    }
    exporter_cls = exporters.get(fmt)
    if exporter_cls is None:
        return "", f"Unsupported export format: {params.format}"
    if fmt == "json":
        exporter_cls().export_to_file(doc, params.path)
    else:
        exporter_cls().export_document(doc, params.path)
    return params.path, None


def _do_import(params: FileImportParams) -> tuple[str, int, str | None]:
    """Import a file as a new document; returns (file_id, count, error|None)."""
    from pathlib import Path

    from tianshangcad.core.session import SessionManager

    suffix = Path(params.path).suffix.lower()
    if suffix == ".json":
        from tianshangcad.io.importers.json_io import JSONImporter

        scene = JSONImporter().import_from_file(params.path)
        doc = JSONImporter().scene_to_document(scene, Path(params.path))
    elif suffix == ".dxf":
        from tianshangcad.io.importers.dxf import DXFImporter

        doc = DXFImporter().import_file(params.path)
    elif suffix == ".step":
        from tianshangcad.io.importers.step import STEPImporter

        doc = STEPImporter().import_file(params.path)
    elif suffix == ".dwg":
        from tianshangcad.io.importers.dwg import DWGImporter

        doc = DWGImporter().import_file(params.path)
    else:
        return "", 0, f"Unsupported import format: {suffix}"
    session = SessionManager().current_session
    session.active_files[doc.file_id] = doc
    session.current_file_id = doc.file_id
    return doc.file_id, len(doc.entities.list()), None


def cad_file_io(input: FileIoInput) -> FileIoOutput:
    """Export or import a document file.

    按 ``action`` 导出（export）当前文档或导入（import）文件为新文档。
    Export formats: step (recommended), dxf, stl, dwg, json. Import
    accepts json/dxf/step/dwg.

    When not to use: to save/load the in-memory scene as JSON use
    ``cad_file_save`` / ``cad_file_open``; ``cad_file_io`` is for
    interop formats. DWG requires the ODA converter (``ODAFC_PATH``).
    """
    params = input.file
    try:
        if params.action == "export":
            path, error = _do_export(params)
            if error is not None:
                return FileIoOutput(action="export", status="error", message=error)
            return FileIoOutput(action="export", path=path, status="success", message="Exported")
        file_id, count, error = _do_import(params)
        if error is not None:
            return FileIoOutput(action="import", status="error", message=error)
        return FileIoOutput(
            action="import",
            path=params.path,
            file_id=file_id,
            object_count=count,
            status="success",
            message="Imported",
        )
    except CADError as exc:
        return FileIoOutput(action=params.action, status="error", message=str(exc))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_file_io", cad_file_io),
]
