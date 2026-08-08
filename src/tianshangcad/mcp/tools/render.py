"""Rendering and preview tools."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.render.renderer_2d import VALID_VIEWS, render_view
from tianshangcad.utils.config import get_settings
from tianshangcad.utils.errors import CADError, CADValidationError


class RenderViewInput(BaseModel):
    """Input for rendering an orthographic PNG view."""

    view: str = Field("top", description="View: top / front / side")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class RenderViewOutput(BaseModel):
    """Output for PNG rendering."""

    path: str = Field(..., description="Path of the written PNG file")
    view: str = Field(..., description="Rendered view")
    dpi: int = Field(..., description="Used DPI")
    size_bytes: int = Field(..., description="PNG size in bytes")
    data_uri: str = Field(..., description="PNG data URI (base64)")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _default_output_path(view: str) -> str:
    temp = get_settings().temp_path
    temp.mkdir(parents=True, exist_ok=True)
    return str(temp / f"cad_view_{view}.png")


def cad_render_view(input: RenderViewInput) -> RenderViewOutput:
    """Render the current document to a PNG in an orthographic view.

    渲染当前文档的正交投影 PNG 视图。
    Views: ``top`` (XY), ``front`` (XZ), ``side`` (YZ). DPI must be between
    72 and 300. Returns the output path and a base64 data URI so the image
    can be embedded directly by MCP clients.
    """
    # Deprecated, merged into cad_render
    try:
        if input.view not in VALID_VIEWS:
            raise CADValidationError(
                f"Unknown view {input.view!r}; expected one of {', '.join(VALID_VIEWS)}",
                code="invalid_view",
            )
        doc = DocumentManager().get_current()
        records = doc.entities.list()
        output = input.output or _default_output_path(input.view)
        png = render_view(
            records,
            view=input.view,
            dpi=input.dpi,
            output=output,
            kernel=doc.entities.kernel,
            title=input.title,
        )
        data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        return RenderViewOutput(
            path=str(Path(output)),
            view=input.view,
            dpi=input.dpi,
            size_bytes=len(png),
            data_uri=data_uri,
            status="success",
            message=f"Rendered {input.view} view ({len(png)} bytes)",
        )
    except CADError as exc:
        return RenderViewOutput(
            path="",
            view=input.view,
            dpi=input.dpi,
            size_bytes=0,
            data_uri="",
            status="error",
            message=str(exc),
        )


# ---------------------------------------------------------------------------
# Aggregate cad_render tool (mode-discriminated union)
# ---------------------------------------------------------------------------


class RenderOrthoParams(BaseModel):
    """Orthographic 2D PNG render."""

    mode: Literal["ortho"] = Field("ortho", description="Render an orthographic 2D view")
    view: str = Field("top", description="View: top / front / side")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class RenderView3DParams(BaseModel):
    """Render a stored 3D view definition to PNG."""

    mode: Literal["view_3d"] = Field("view_3d", description="Render a stored 3D view")
    view_id: str = Field(..., description="View id or name to render")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class RenderSectionParams(BaseModel):
    """Render a plane-section view of the document."""

    mode: Literal["section"] = Field("section", description="Render a plane section")
    plane: str = Field(..., description="Section plane: XY / YZ / XZ")
    offset: float = Field(0.0, description="Plane offset along its normal")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class RenderExplodeParams(BaseModel):
    """Render an exploded view of the document."""

    mode: Literal["explode"] = Field("explode", description="Render an exploded view")
    offset_x: float = Field(0.0, ge=0, description="X explode factor")
    offset_y: float = Field(0.0, ge=0, description="Y explode factor")
    offset_z: float = Field(0.0, ge=0, description="Z explode factor")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class RenderAnimationParams(BaseModel):
    """Render an orbit / turntable GIF animation."""

    mode: Literal["animation"] = Field("animation", description="Render an orbit animation")
    frames: int = Field(48, description="Number of frames within [2, 96]")
    fps: int = Field(10, description="Frames per second within [1, 30]")
    anim_mode: str = Field("orbit", description="Animation mode: orbit / turntable")
    total_degrees: float = Field(360.0, description="Total rotation in degrees")
    output: str | None = Field(None, description="Optional output GIF path")
    title: str | None = Field(None, description="Optional plot title")


class RenderWebglParams(BaseModel):
    """Return an incremental WebGL synchronization delta."""

    mode: Literal["webgl"] = Field("webgl", description="Emit a WebGL sync delta")
    previous_ids: list[str] = Field(
        default_factory=list, description="Object ids the client already holds"
    )
    include_full: bool = Field(False, description="Also include the full snapshot")


RenderParams = Annotated[
    RenderOrthoParams
    | RenderView3DParams
    | RenderSectionParams
    | RenderExplodeParams
    | RenderAnimationParams
    | RenderWebglParams,
    Field(discriminator="mode"),
]


class RenderInput(BaseModel):
    """Input for the aggregate render tool.

    聚合渲染工具。``mode`` 决定渲染类型，各 mode 使用各自的参数字段：
    - ``ortho``: ``view``/``dpi``/``output``/``title``
    - ``view_3d``: ``view_id``/``dpi``/``output``/``title``
    - ``section``: ``plane``/``offset``/``dpi``/``output``/``title``
    - ``explode``: ``offset_x``/``offset_y``/``offset_z``/``dpi``/``output``/``title``
    - ``animation``: ``frames``/``fps``/``anim_mode``/``total_degrees``/``output``/``title``
    - ``webgl``: ``previous_ids``/``include_full``
    """

    render: RenderParams = Field(
        ...,
        description=(
            "Render request, discriminated by `mode`: ortho, view_3d, "
            "section, explode, animation or webgl."
        ),
    )


class RenderOutput(BaseModel):
    """Output of the aggregate render tool."""

    path: str = Field("", description="Path of the written output file")
    mode: str = Field(..., description="Render mode used")
    size_bytes: int = Field(0, description="Output size in bytes")
    data_uri: str = Field("", description="Output data URI (base64)")
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Extra mode-specific data (webgl deltas)"
    )
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _render_error(mode: str, message: str) -> RenderOutput:
    return RenderOutput(mode=mode, status="error", message=message)


def cad_render(input: RenderInput) -> RenderOutput:
    """Render the document in a selected mode.

    按 ``mode`` 渲染当前文档：
    - ortho：2D 正交投影 PNG（top/front/side）
    - view_3d：按存储的三维视图定义渲染 PNG
    - section：平面剖切 PNG（plane=XY/YZ/XZ）
    - explode：爆炸视图 PNG
    - animation：orbit/turntable GIF 动画
    - webgl：WebGL 增量同步 delta

    When not to use: ``cad_render`` produces images / sync deltas only. To
    store or edit a named view *definition* before rendering use
    ``cad_view``; for drawing-sheet exports (SVG/DXF/PDF) use
    ``cad_drawing`` (action=export); for interop geometry files use
    ``cad_file`` (export).
    """
    try:
        params = input.render
        doc = DocumentManager().get_current()
        records = doc.entities.list()

        if params.mode == "ortho":
            if params.view not in VALID_VIEWS:
                raise CADValidationError(
                    f"Unknown view {params.view!r}; expected one of {', '.join(VALID_VIEWS)}",
                    code="invalid_view",
                )
            output = params.output or _default_output_path(params.view)
            png = render_view(
                records,
                view=params.view,
                dpi=params.dpi,
                output=output,
                kernel=doc.entities.kernel,
                title=params.title,
            )
            return RenderOutput(
                path=str(Path(output)),
                mode="ortho",
                size_bytes=len(png),
                data_uri="data:image/png;base64," + base64.b64encode(png).decode("ascii"),
                status="success",
                message=f"Rendered {params.view} view ({len(png)} bytes)",
            )

        if params.mode == "webgl":
            from tianshangcad.render.webgl_exporter import export_webgl_delta

            delta = export_webgl_delta(
                params.previous_ids,
                records,
                kernel=doc.entities.kernel,
                include_full=params.include_full,
            )
            full_uri = ""
            if params.include_full and delta.get("full"):
                import json

                payload = json.dumps(delta["full"]).encode("utf-8")
                full_uri = (
                    "data:application/json;base64," + base64.b64encode(payload).decode("ascii")
                )
            return RenderOutput(
                mode="webgl",
                data_uri=full_uri,
                payload={
                    "added": delta["added"],
                    "removed": delta["removed"],
                    "updated": delta["updated"],
                    "object_count": delta["objectCount"],
                },
                status="success",
                message=(
                    f"{len(delta['added'])} added, {len(delta['removed'])} removed, "
                    f"{len(delta['updated'])} updated"
                ),
            )

        if params.mode == "view_3d":
            from tianshangcad.schemas.view3d import fit_camera_to_bounds

            view = _resolve_view(doc, params.view_id)
            camera = view.camera
            if view.fit_to_bounds and records:
                bbox = DocumentManager._compute_bbox(doc)
                fitted = fit_camera_to_bounds(bbox)
                camera = camera.model_copy(
                    update={"distance": fitted.distance, "target": fitted.target}
                )
            from tianshangcad.render.renderer_3d import render_3d_triangles

            output = params.output or _default_output_path(f"view_{view.name}.png")
            png = render_3d_triangles(
                _mesh_triangles(records, doc.entities.kernel),
                dpi=params.dpi,
                output=output,
                title=params.title or f"View: {view.name}",
                camera=camera,
                projection=view.projection,
            )
            return RenderOutput(
                path=str(Path(output)),
                mode="view_3d",
                size_bytes=len(png),
                data_uri="data:image/png;base64," + base64.b64encode(png).decode("ascii"),
                status="success",
                message=f"Rendered view {view.name} ({len(png)} bytes)",
            )

        if params.mode == "section":
            from tianshangcad.render.renderer_3d import render_3d_triangles
            from tianshangcad.render.section import section_mesh
            from tianshangcad.schemas.view3d import SectionPlane

            if params.plane not in ("XY", "YZ", "XZ"):
                raise CADValidationError("plane must be one of XY, YZ, XZ", code="invalid_plane")
            plane = SectionPlane(plane=params.plane, offset=params.offset)
            kept, cut = section_mesh(records, plane, kernel=doc.entities.kernel)
            output = params.output or _default_output_path(f"section_{params.plane}.png")
            png = render_3d_triangles(
                kept,
                dpi=params.dpi,
                output=output,
                title=params.title or f"Section {params.plane} @ {params.offset}",
                cut_edges=cut,
            )
            return RenderOutput(
                path=str(Path(output)),
                mode="section",
                size_bytes=len(png),
                data_uri="data:image/png;base64," + base64.b64encode(png).decode("ascii"),
                status="success",
                message=f"Rendered section {params.plane} ({len(png)} bytes)",
            )

        if params.mode == "explode":
            from tianshangcad.render.explode import explode_mesh
            from tianshangcad.render.renderer_3d import render_3d_triangles
            from tianshangcad.schemas.view3d import ExplodeSpec

            explode_spec = ExplodeSpec(
                offset_x=params.offset_x, offset_y=params.offset_y, offset_z=params.offset_z
            )
            triangles = explode_mesh(records, explode_spec, kernel=doc.entities.kernel)
            output = params.output or _default_output_path("explode.png")
            png = render_3d_triangles(
                triangles,
                dpi=params.dpi,
                output=output,
                title=params.title or "Exploded view",
            )
            return RenderOutput(
                path=str(Path(output)),
                mode="explode",
                size_bytes=len(png),
                data_uri="data:image/png;base64," + base64.b64encode(png).decode("ascii"),
                status="success",
                message=f"Rendered exploded view ({len(png)} bytes)",
            )

        if params.mode == "animation":
            from tianshangcad.render.animation import render_orbit_gif
            from tianshangcad.schemas.view3d import AnimationSpec

            if params.anim_mode not in ("orbit", "turntable"):
                raise CADValidationError(
                    "anim_mode must be orbit or turntable", code="invalid_mode"
                )
            anim_spec = AnimationSpec(
                mode=params.anim_mode,
                frames=params.frames,
                fps=params.fps,
                total_degrees=params.total_degrees,
            )
            output = params.output or _default_output_path("orbit.gif")
            gif = render_orbit_gif(
                records,
                frames=params.frames,
                fps=params.fps,
                output=output,
                kernel=doc.entities.kernel,
                spec=anim_spec,
                title=params.title,
            )
            return RenderOutput(
                path=str(Path(output)),
                mode="animation",
                size_bytes=len(gif),
                data_uri="data:image/gif;base64," + base64.b64encode(gif).decode("ascii"),
                status="success",
                message=f"Rendered {params.frames}-frame GIF ({len(gif)} bytes)",
            )

        raise CADValidationError(f"Unknown render mode {params.mode!r}", code="unknown_mode")
    except CADError as exc:
        return _render_error(input.render.mode, str(exc))


def _resolve_view(doc: Any, view_id: str) -> Any:
    manager = doc.views
    view = manager.get_by_name(view_id)
    if view is not None:
        return view
    return manager.get(view_id)


def _mesh_triangles(records: list[Any], kernel: Any) -> list[list[list[float]]]:
    """Return the tessellated triangles of all solid records."""
    triangles: list[list[list[float]]] = []
    for record in records:
        shape = record.shape
        if shape["kind"] in ("line", "circle", "arc"):
            continue
        vertices, faces = kernel.tessellate(shape)
        for face in faces:
            if len(face) < 3:
                continue
            triangles.append(
                [
                    [vertices[face[0]][0], vertices[face[0]][1], vertices[face[0]][2]],
                    [vertices[face[1]][0], vertices[face[1]][1], vertices[face[1]][2]],
                    [vertices[face[2]][0], vertices[face[2]][1], vertices[face[2]][2]],
                ]
            )
    return triangles


TOOLS: list[tuple[str, Any]] = [
    ("cad_render", cad_render),
]

