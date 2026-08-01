"""Rendering commands: 2D orthographic PNG, 3D preview and WebGL export."""

from __future__ import annotations

from pathlib import Path

import typer

from cad_mcp_server.cli.utils import catch_errors, fail
from cad_mcp_server.core.document import DocumentManager

app = typer.Typer(help="Rendering output")


@app.command("view")
@catch_errors
def cmd_view(
    view: str = typer.Option("top", "--view", "-v", help="View: top / front / side"),
    dpi: int = typer.Option(96, "--dpi", help="Resolution in DPI (72-300)"),
    output: str = typer.Option("preview.png", "--output", "-o", help="Output PNG path"),
) -> None:
    """Render the current document to a 2D orthographic PNG."""
    from cad_mcp_server.render.renderer_2d import VALID_VIEWS, render_view

    if view not in VALID_VIEWS:
        fail(f"Unknown view {view!r}; expected one of {', '.join(VALID_VIEWS)}")
    doc = DocumentManager().get_current()
    render_view(
        doc.entities.list(),
        view=view,
        dpi=dpi,
        output=output,
        kernel=doc.entities.kernel,
    )
    typer.echo(f"Rendered {view} view -> {output}")


@app.command("3d")
@catch_errors
def cmd_3d(
    dpi: int = typer.Option(96, "--dpi", help="Resolution in DPI (72-300)"),
    output: str = typer.Option("preview3d.png", "--output", "-o", help="Output PNG path"),
) -> None:
    """Render the current document as a shaded 3D preview PNG."""
    from cad_mcp_server.render.renderer_3d import render_3d

    doc = DocumentManager().get_current()
    render_3d(
        doc.entities.list(),
        dpi=dpi,
        output=output,
        kernel=doc.entities.kernel,
    )
    typer.echo(f"Rendered 3D preview -> {output}")


@app.command("webgl")
@catch_errors
def cmd_webgl(
    output: str = typer.Option("viewer_data.json", "--output", "-o", help="Output JSON path"),
    viewer: str | None = typer.Option(
        None, "--viewer", help="Also write the Three.js viewer HTML to this path"
    ),
) -> None:
    """Export the current document to Three.js BufferGeometry JSON."""
    from cad_mcp_server.render.webgl_exporter import export_webgl_file, viewer_html

    doc = DocumentManager().get_current()
    path = export_webgl_file(doc.entities.list(), output, kernel=doc.entities.kernel)
    typer.echo(f"Exported WebGL data -> {path}")
    if viewer:
        target = Path(viewer)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(viewer_html(), encoding="utf-8")
        typer.echo(f"Viewer HTML -> {target}")


@app.command("status")
@catch_errors
def cmd_status() -> None:
    """Show rendering subsystem status."""
    typer.echo("Rendering engine: matplotlib (Agg) + Three.js WebGL export")
