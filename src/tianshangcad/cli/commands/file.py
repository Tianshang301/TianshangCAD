"""File operations: new, open, save, close, list, info."""

from __future__ import annotations

import typer

from tianshangcad.cli.utils import catch_errors, get_document
from tianshangcad.core.document import DocumentManager

app = typer.Typer(help="File operations")


@app.command("new")
@catch_errors
def cmd_new(
    filename: str = typer.Argument(..., help="File name with extension"),
    template: str | None = typer.Option(None, "--template", "-t", help="Template file"),
    unit: str = typer.Option("mm", "--unit", "-u", help="Unit (mm/cm/m/in/ft)"),
) -> None:
    """Create a new CAD file."""
    doc_mgr = DocumentManager()
    file_id = doc_mgr.create(filename=filename, template=template, unit=unit)
    typer.echo(f"File created: {filename} (ID: {file_id})")


@app.command("open")
@catch_errors
def cmd_open(
    filepath: str = typer.Argument(..., help="File path"),
    read_only: bool = typer.Option(False, "--read-only", "-r", help="Read-only mode"),
) -> None:
    """Open an existing CAD file."""
    doc_mgr = DocumentManager()
    file_id = doc_mgr.open(filepath)
    doc = doc_mgr.info(file_id)
    mode = "read-only" if read_only else "read-write"
    typer.echo(f"Opened {filepath} (ID: {file_id}, {mode}, {doc['entity_count']} objects)")


@app.command("save")
@catch_errors
def cmd_save(
    path: str | None = typer.Argument(None, help="Output file path"),
) -> None:
    """Save the current file."""
    doc_mgr = DocumentManager()
    get_document()
    saved = doc_mgr.save(path=path)
    typer.echo(f"Saved: {saved}")


@app.command("close")
@catch_errors
def cmd_close() -> None:
    """Close the current file."""
    doc_mgr = DocumentManager()
    doc = doc_mgr.get_current()
    doc_mgr.close(doc.file_id)
    typer.echo(f"Closed: {doc.filename}")


@app.command("list")
@catch_errors
def cmd_list() -> None:
    """List open files."""
    doc_mgr = DocumentManager()
    docs = doc_mgr.list()
    if not docs:
        typer.echo("No open files")
        return
    for doc in docs:
        state = " (dirty)" if doc["dirty"] else ""
        line = f"{doc['file_id']}  {doc['filename']}  unit={doc['unit']}"
        typer.echo(f"{line}  objects={doc['entity_count']}{state}")


@app.command("info")
@catch_errors
def cmd_info() -> None:
    """Show details of the current file."""
    doc_mgr = DocumentManager()
    info = doc_mgr.info()
    typer.echo(f"File:     {info['filename']}")
    typer.echo(f"ID:       {info['file_id']}")
    typer.echo(f"Path:     {info['path'] or '<unsaved>'}")
    typer.echo(f"Unit:     {info['unit']}")
    typer.echo(f"Objects:  {info['entity_count']}")
    typer.echo(f"Layers:   {info['layer_count']}")
    bbox = info["bbox"]
    typer.echo(f"Bounds:   min={bbox['min']}  max={bbox['max']}")


@app.command("export")
@catch_errors
def cmd_export(
    fmt: str = typer.Option(
        "step",
        "--format",
        "-f",
        help="Output format: step (recommended) / dxf / stl / json / dwg",
    ),
    output: str = typer.Option(..., "--output", "-o", help="Output file path"),
) -> None:
    """Export the current file (step / dxf / stl / json / dwg)."""
    doc = get_document()
    if fmt == "dxf":
        from tianshangcad.io.exporters.dxf import DXFExporter

        DXFExporter().export_document(doc, output)
    elif fmt == "stl":
        from tianshangcad.io.exporters.stl import STLExporter

        STLExporter().export_document(doc, output)
    elif fmt == "json":
        from tianshangcad.io.exporters.json_io import JSONExporter

        JSONExporter().export_to_file(doc, output)
    elif fmt == "step":
        from tianshangcad.io.exporters.step import STEPExporter

        STEPExporter().export_document(doc, output)
    elif fmt == "dwg":
        from tianshangcad.io.exporters.dwg import DWGExporter

        DWGExporter().export_document(doc, output)
    else:
        from tianshangcad.cli.utils import fail

        fail(f"Unsupported export format: {fmt}")
    typer.echo(f"Exported: {output}")


@app.command("import")
@catch_errors
def cmd_import(
    filepath: str = typer.Argument(..., help="File path to import"),
) -> None:
    """Import a file (json / dxf / step / dwg) as a new document."""
    from pathlib import Path

    from tianshangcad.cli.utils import fail
    from tianshangcad.core.session import SessionManager

    suffix = Path(filepath).suffix.lower()
    if suffix == ".json":
        from tianshangcad.io.importers.json_io import JSONImporter

        scene = JSONImporter().import_from_file(filepath)
        doc = JSONImporter().scene_to_document(scene, Path(filepath))
    elif suffix == ".dxf":
        from tianshangcad.io.importers.dxf import DXFImporter

        doc = DXFImporter().import_file(filepath)
    elif suffix == ".step":
        from tianshangcad.io.importers.step import STEPImporter

        doc = STEPImporter().import_file(filepath)
    elif suffix == ".dwg":
        from tianshangcad.io.importers.dwg import DWGImporter

        doc = DWGImporter().import_file(filepath)
    else:
        fail(f"Unsupported import format: {suffix}")
    session = SessionManager().current_session
    session.active_files[doc.file_id] = doc
    session.current_file_id = doc.file_id
    typer.echo(f"Imported {filepath}: {len(doc.entities.list())} objects")
