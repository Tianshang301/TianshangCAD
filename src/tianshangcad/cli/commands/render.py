"""Rendering commands: 2D orthographic PNG, 3D preview and WebGL export."""

from __future__ import annotations

from pathlib import Path

import typer

from tianshangcad.cli.utils import catch_errors, fail
from tianshangcad.core.document import DocumentManager

app = typer.Typer(help="Rendering output")


@app.command("view")
@catch_errors
def cmd_view(
    view: str = typer.Option("top", "--view", "-v", help="View: top / front / side"),
    dpi: int = typer.Option(96, "--dpi", help="Resolution in DPI (72-300)"),
    output: str = typer.Option("preview.png", "--output", "-o", help="Output PNG path"),
) -> None:
    """Render the current document to a 2D orthographic PNG."""
    from tianshangcad.render.renderer_2d import VALID_VIEWS, render_view

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
    from tianshangcad.render.renderer_3d import render_3d

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
    from tianshangcad.render.webgl_exporter import export_webgl_file, viewer_html

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


@app.command("view3d")
@catch_errors
def cmd_view3d(
    view: str = typer.Option(
        "iso",
        "--view",
        "-v",
        help="View id/name or iso/top/front/side/back/bottom",
    ),
    dpi: int = typer.Option(96, "--dpi", help="Resolution in DPI (72-300)"),
    output: str = typer.Option("view3d.png", "--output", "-o", help="Output PNG path"),
    orthographic: bool = typer.Option(
        False, "--orthographic", help="Use orthographic projection"
    ),
) -> None:
    """Render the document from a 3D view definition or a named view."""
    from tianshangcad.mcp.tools.view3d import (
        ViewRenderInput,
        cad_view_3d_render,
    )
    from tianshangcad.schemas.view3d import NAMED_VIEWS, named_view

    doc = DocumentManager().get_current()
    manager = doc.views
    stored = manager.get_by_name(view)
    if stored is None:
        try:
            stored = manager.get(view)
        except Exception:
            stored = None

    if stored is not None:
        result = cad_view_3d_render(ViewRenderInput(view_id=stored.view_id, dpi=dpi, output=output))
        if result.status != "success":
            fail(result.message or "view render failed")
            return
        typer.echo(f"Rendered 3D view {view} -> {result.path}")
        return

    if view.lower() not in NAMED_VIEWS:
        fail(f"Unknown view {view!r}; not a stored view or named view")
        return
    definition = named_view(view.lower()).model_copy(
        update={"projection": "orthographic" if orthographic else "perspective"}
    )
    created = manager.create(view.lower(), definition=definition)
    try:
        result = cad_view_3d_render(ViewRenderInput(view_id=created, dpi=dpi, output=output))
        if result.status != "success":
            fail(result.message or "view render failed")
            return
        typer.echo(f"Rendered 3D view {view} -> {result.path}")
    finally:
        manager.delete(created)


@app.command("section")
@catch_errors
def cmd_section(
    plane: str = typer.Option("XY", "--plane", "-p", help="Section plane: XY / YZ / XZ"),
    offset: float = typer.Option(0.0, "--offset", help="Plane offset along its normal"),
    dpi: int = typer.Option(96, "--dpi", help="Resolution in DPI (72-300)"),
    output: str = typer.Option("section.png", "--output", "-o", help="Output PNG path"),
) -> None:
    """Render a plane-section view of the document."""
    from tianshangcad.mcp.tools.view3d import ViewSectionInput, cad_view_section

    result = cad_view_section(
        ViewSectionInput(plane=plane, offset=offset, dpi=dpi, output=output)
    )
    if result.status != "success":
        fail(result.message or "section render failed")
    typer.echo(f"Rendered section {plane} @ {offset} -> {result.path}")


@app.command("explode")
@catch_errors
def cmd_explode(
    x: float = typer.Option(0.0, "--x", help="X explode factor"),
    y: float = typer.Option(0.0, "--y", help="Y explode factor"),
    z: float = typer.Option(0.0, "--z", help="Z explode factor"),
    dpi: int = typer.Option(96, "--dpi", help="Resolution in DPI (72-300)"),
    output: str = typer.Option("explode.png", "--output", "-o", help="Output PNG path"),
) -> None:
    """Render an exploded view of the document."""
    from tianshangcad.mcp.tools.view3d import ViewExplodeInput, cad_view_explode

    result = cad_view_explode(
        ViewExplodeInput(offset_x=x, offset_y=y, offset_z=z, dpi=dpi, output=output)
    )
    if result.status != "success":
        fail(result.message or "explode render failed")
    typer.echo(f"Rendered exploded view -> {result.path}")


@app.command("gif")
@catch_errors
def cmd_gif(
    frames: int = typer.Option(48, "--frames", "-n", help="Number of frames (2-96)"),
    fps: int = typer.Option(10, "--fps", help="Frames per second (1-30)"),
    mode: str = typer.Option("orbit", "--mode", "-m", help="Animation mode: orbit / turntable"),
    output: str = typer.Option("orbit.gif", "--output", "-o", help="Output GIF path"),
) -> None:
    """Render an orbit / turntable GIF animation."""
    from tianshangcad.mcp.tools.view3d import ViewAnimationInput, cad_view_animation

    result = cad_view_animation(
        ViewAnimationInput(frames=frames, fps=fps, mode=mode, output=output)
    )
    if result.status != "success":
        fail(result.message or "animation render failed")
    typer.echo(f"Rendered {frames}-frame GIF -> {result.path}")


@app.command("views")
@catch_errors
def cmd_views() -> None:
    """List the 3D view definitions in the current document."""
    from tianshangcad.mcp.tools.view3d import ViewListInput, cad_view_3d_list

    result = cad_view_3d_list(ViewListInput())
    if result.status != "success":
        fail(result.message or "list failed")
    for view in result.views:
        typer.echo(f"{view['name']:<12} {view['view_id']:<16} {view['projection']}")
    typer.echo(f"{result.count} view(s)")
