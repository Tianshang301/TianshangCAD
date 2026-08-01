"""3D view toolchain MCP tools.

Create / read / list / update / delete JSON-defined 3D views, render them
to PNG or GIF, apply section / explode effects, and emit incremental
WebGL sync deltas.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from cad_mcp_server.core.document import DocumentManager, DocumentState
from cad_mcp_server.render.animation import render_orbit_gif
from cad_mcp_server.render.explode import explode_mesh
from cad_mcp_server.render.renderer_3d import render_3d_triangles
from cad_mcp_server.render.section import section_mesh
from cad_mcp_server.render.webgl_exporter import export_webgl_delta
from cad_mcp_server.schemas.view3d import (
    AnimationSpec,
    CameraPose,
    ExplodeSpec,
    SectionPlane,
    View3DDefinition,
    fit_camera_to_bounds,
)
from cad_mcp_server.utils.config import get_settings
from cad_mcp_server.utils.errors import CADError, CADValidationError

NAMED_VIEW_NAMES = ("iso", "top", "front", "side", "back", "bottom")


class ViewCreateInput(BaseModel):
    """Input for creating a 3D view definition."""

    name: str = Field(..., description="View name (unique per document)")
    projection: str = Field("perspective", description="perspective / orthographic")
    camera: CameraPose | None = Field(None, description="Optional camera pose")
    section: SectionPlane | None = Field(None, description="Optional section plane")
    explode: ExplodeSpec | None = Field(None, description="Optional explode offsets")
    fit_to_bounds: bool = Field(True, description="Auto-frame the model bounds")
    view_id: str | None = Field(None, description="Optional explicit view id")


class ViewReadOutput(BaseModel):
    """Output for reading a view definition."""

    view: dict[str, Any] | None = Field(None, description="The view definition")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ViewListOutput(BaseModel):
    """Output for listing view definitions."""

    views: list[dict[str, Any]] = Field(default_factory=list, description="View definitions")
    count: int = Field(..., description="Number of views")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ViewUpdateInput(BaseModel):
    """Input for updating a view definition."""

    view_id: str = Field(..., description="View id to update")
    name: str | None = Field(None, description="New name (optional)")
    projection: str | None = Field(None, description="perspective / orthographic")
    camera: CameraPose | None = Field(None, description="New camera pose")
    section: SectionPlane | None = Field(None, description="New section plane (null clears)")
    explode: ExplodeSpec | None = Field(None, description="New explode offsets (null clears)")


class ViewDeleteInput(BaseModel):
    """Input for deleting a view definition."""

    view_id: str = Field(..., description="View id to delete")


class ViewRenderInput(BaseModel):
    """Input for rendering a view to PNG."""

    view_id: str = Field(..., description="View id to render")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class ViewRenderOutput(BaseModel):
    """Output for PNG rendering."""

    path: str = Field(..., description="Path of the written PNG file")
    view_id: str = Field(..., description="Rendered view id")
    size_bytes: int = Field(..., description="PNG size in bytes")
    data_uri: str = Field(..., description="PNG data URI (base64)")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class ViewSectionInput(BaseModel):
    """Input for rendering a section view."""

    plane: str = Field(..., description="Section plane: XY / YZ / XZ")
    offset: float = Field(0.0, description="Plane offset along its normal")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class ViewExplodeInput(BaseModel):
    """Input for rendering an exploded view."""

    offset_x: float = Field(0.0, ge=0, description="X explode factor")
    offset_y: float = Field(0.0, ge=0, description="Y explode factor")
    offset_z: float = Field(0.0, ge=0, description="Z explode factor")
    dpi: int = Field(96, description="Resolution in DPI within [72, 300]")
    output: str | None = Field(None, description="Optional output PNG path")
    title: str | None = Field(None, description="Optional plot title")


class ViewAnimationInput(BaseModel):
    """Input for rendering an orbit GIF."""

    frames: int = Field(48, description="Number of frames within [2, 96]")
    fps: int = Field(10, description="Frames per second within [1, 30]")
    mode: str = Field("orbit", description="Animation mode: orbit / turntable")
    total_degrees: float = Field(360.0, description="Total rotation in degrees")
    output: str | None = Field(None, description="Optional output GIF path")
    title: str | None = Field(None, description="Optional plot title")


class ViewAnimationOutput(BaseModel):
    """Output for GIF animation rendering."""

    path: str = Field(..., description="Path of the written GIF file")
    frames: int = Field(..., description="Number of frames")
    size_bytes: int = Field(..., description="GIF size in bytes")
    data_uri: str = Field(..., description="GIF data URI (base64)")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class WebGLSyncInput(BaseModel):
    """Input for incremental WebGL sync."""

    previous_ids: list[str] = Field(
        default_factory=list, description="Object ids the client already holds"
    )
    include_full: bool = Field(False, description="Also include the full snapshot")


class WebGLSyncOutput(BaseModel):
    """Output for incremental WebGL sync."""

    added: list[str] = Field(default_factory=list, description="New object ids")
    removed: list[str] = Field(default_factory=list, description="Removed object ids")
    updated: list[str] = Field(default_factory=list, description="Updated object ids")
    object_count: int = Field(..., description="Current object count")
    has_full: bool = Field(False, description="Whether the full snapshot is included")
    full_data_uri: str = Field("", description="Optional full snapshot as data URI")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _doc() -> DocumentState:
    return DocumentManager().get_current()


def _default_output_path(suffix: str, stem: str) -> str:
    temp = get_settings().temp_path
    temp.mkdir(parents=True, exist_ok=True)
    return str(temp / f"cad_{stem}{suffix}")


def cad_view_3d_create(input: ViewCreateInput) -> ViewReadOutput:
    """Create a 3D view definition.

    创建三维视图定义。基于投影类型与球面相机位姿，可附加剖面与爆炸
    视图参数。``name`` 在同一文档内必须唯一。
    """
    try:
        if input.projection not in ("perspective", "orthographic"):
            raise CADValidationError(
                "projection must be perspective or orthographic", code="invalid_projection"
            )
        definition = View3DDefinition(
            view_id=input.view_id or "pending",
            name=input.name,
            projection=input.projection,
            camera=input.camera or CameraPose(),
            section=input.section,
            explode=input.explode,
            fit_to_bounds=input.fit_to_bounds,
        )
        view_id = _doc().views.create(input.name, definition=definition, view_id=input.view_id)
        view = _doc().views.get(view_id)
        return ViewReadOutput(
            view=view.to_dict(),
            status="success",
            message=f"View {input.name!r} created ({view_id})",
        )
    except CADError as exc:
        return ViewReadOutput(status="error", message=str(exc))


def cad_view_3d_read(input: ViewReadInput) -> ViewReadOutput:
    """Read a 3D view definition by id or name.

    按 id 或名称读取三维视图定义，返回相机位姿、投影与剖切/爆炸参数。
    """
    try:
        view = _view_from_input(input)
        return ViewReadOutput(view=view.to_dict(), status="success")
    except CADError as exc:
        return ViewReadOutput(status="error", message=str(exc))


class ViewReadInput(BaseModel):
    """Input for reading a view definition."""

    view_id: str = Field(..., description="View id or name to read")


def _view_from_input(input: ViewReadInput) -> View3DDefinition:
    manager = _doc().views
    view = manager.get_by_name(input.view_id)
    if view is not None:
        return view
    return manager.get(input.view_id)


def cad_view_3d_list(input: ViewListInput) -> ViewListOutput:
    """List all 3D view definitions in the document.

    列出文档内全部三维视图定义（名称、投影、相机位姿概要）。
    """
    try:
        views = [view.to_dict() for view in _doc().views.list()]
        return ViewListOutput(
            views=views,
            count=len(views),
            status="success",
            message=f"{len(views)} view(s)",
        )
    except CADError as exc:
        return ViewListOutput(count=0, status="error", message=str(exc))


class ViewListInput(BaseModel):
    """Input for listing view definitions."""

    pass


def cad_view_3d_update(input: ViewUpdateInput) -> ViewReadOutput:
    """Update a 3D view definition.

    更新三维视图定义。传入的字段会被合并，未传入字段保持不变。
    ``section=None`` 或 ``explode=None`` 会清除对应配置。
    """
    try:
        changes: dict[str, Any] = {}
        if input.name is not None:
            changes["name"] = input.name
        if input.projection is not None:
            if input.projection not in ("perspective", "orthographic"):
                raise CADValidationError(
                    "projection must be perspective or orthographic", code="invalid_projection"
                )
            changes["projection"] = input.projection
        if input.camera is not None:
            changes["camera"] = input.camera
        if input.section is not None:
            changes["section"] = input.section
        if input.explode is not None:
            changes["explode"] = input.explode
        view = _doc().views.update(_resolve_view(input.view_id).view_id, **changes)
        return ViewReadOutput(
            view=view.to_dict(),
            status="success",
            message=f"View {input.view_id} updated",
        )
    except CADError as exc:
        return ViewReadOutput(status="error", message=str(exc))


def cad_view_3d_delete(input: ViewDeleteInput) -> ViewReadOutput:
    """Delete a 3D view definition.

    删除三维视图定义。此操作不可撤销。
    """
    try:
        _doc().views.delete(_resolve_view(input.view_id).view_id)
        return ViewReadOutput(status="success", message=f"View {input.view_id} deleted")
    except CADError as exc:
        return ViewReadOutput(status="error", message=str(exc))


def _resolve_view(view_id: str) -> View3DDefinition:
    manager = _doc().views
    view = manager.get_by_name(view_id)
    if view is not None:
        return view
    return manager.get(view_id)


def _apply_view_settings(view: View3DDefinition, records: list[Any]) -> CameraPose:
    """Return the camera pose for a view, auto-framing when requested."""
    camera = view.camera
    if view.fit_to_bounds and records:
        doc = _doc()
        bbox = DocumentManager._compute_bbox(doc)
        fitted = fit_camera_to_bounds(bbox)
        camera = camera.model_copy(
            update={"distance": fitted.distance, "target": fitted.target}
        )
    return camera


def cad_view_3d_render(input: ViewRenderInput) -> ViewRenderOutput:
    """Render a 3D view to a PNG.

    以指定视图的相机位姿渲染当前文档为 PNG 图片，返回 base64 data URI。
    """
    try:
        view = _resolve_view(input.view_id)
        doc = _doc()
        records = doc.entities.list()
        camera = _apply_view_settings(view, records)
        output = input.output or _default_output_path(".png", f"view_{view.name}")
        png = render_3d_triangles(
            _mesh_triangles(records, doc.entities.kernel),
            dpi=input.dpi,
            output=output,
            title=input.title or f"View: {view.name}",
            camera=camera,
            projection=view.projection,
        )
        data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        return ViewRenderOutput(
            path=str(Path(output)),
            view_id=view.view_id,
            size_bytes=len(png),
            data_uri=data_uri,
            status="success",
            message=f"Rendered view {view.name} ({len(png)} bytes)",
        )
    except CADError as exc:
        return ViewRenderOutput(
            path="",
            view_id=input.view_id,
            size_bytes=0,
            data_uri="",
            status="error",
            message=str(exc),
        )


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


def cad_view_section(input: ViewSectionInput) -> ViewRenderOutput:
    """Render a plane-section view of the document.

    渲染平面剖切视图。``plane`` 为 XY/YZ/XZ，``offset`` 为沿法向偏移。
    """
    try:
        if input.plane not in ("XY", "YZ", "XZ"):
            raise CADValidationError("plane must be one of XY, YZ, XZ", code="invalid_plane")
        doc = _doc()
        records = doc.entities.list()
        plane = SectionPlane(plane=input.plane, offset=input.offset)
        kept, cut = section_mesh(records, plane, kernel=doc.entities.kernel)
        output = input.output or _default_output_path(".png", f"section_{input.plane}")
        png = render_3d_triangles(
            kept,
            dpi=input.dpi,
            output=output,
            title=input.title or f"Section {input.plane} @ {input.offset}",
            cut_edges=cut,
        )
        data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        return ViewRenderOutput(
            path=str(Path(output)),
            view_id=f"section_{input.plane}",
            size_bytes=len(png),
            data_uri=data_uri,
            status="success",
            message=f"Rendered section {input.plane} ({len(png)} bytes)",
        )
    except CADError as exc:
        return ViewRenderOutput(
            path="",
            view_id="",
            size_bytes=0,
            data_uri="",
            status="error",
            message=str(exc),
        )


def cad_view_explode(input: ViewExplodeInput) -> ViewRenderOutput:
    """Render an exploded view of the document.

    渲染爆炸视图。各轴偏移量是模型半径的倍数。
    """
    try:
        doc = _doc()
        records = doc.entities.list()
        spec = ExplodeSpec(
            offset_x=input.offset_x, offset_y=input.offset_y, offset_z=input.offset_z
        )
        triangles = explode_mesh(records, spec, kernel=doc.entities.kernel)
        output = input.output or _default_output_path(".png", "explode")
        png = render_3d_triangles(
            triangles,
            dpi=input.dpi,
            output=output,
            title=input.title or "Exploded view",
        )
        data_uri = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
        return ViewRenderOutput(
            path=str(Path(output)),
            view_id="explode",
            size_bytes=len(png),
            data_uri=data_uri,
            status="success",
            message=f"Rendered exploded view ({len(png)} bytes)",
        )
    except CADError as exc:
        return ViewRenderOutput(
            path="",
            view_id="",
            size_bytes=0,
            data_uri="",
            status="error",
            message=str(exc),
        )


def cad_view_animation(input: ViewAnimationInput) -> ViewAnimationOutput:
    """Render an orbit / turntable GIF animation.

    渲染绕模型旋转的 GIF 动画。``mode`` 为 orbit 或 turntable。
    """
    try:
        if input.mode not in ("orbit", "turntable"):
            raise CADValidationError("mode must be orbit or turntable", code="invalid_mode")
        doc = _doc()
        records = doc.entities.list()
        spec = AnimationSpec(
            mode=input.mode,
            frames=input.frames,
            fps=input.fps,
            total_degrees=input.total_degrees,
        )
        output = input.output or _default_output_path(".gif", "orbit")
        gif = render_orbit_gif(
            records,
            frames=input.frames,
            fps=input.fps,
            output=output,
            kernel=doc.entities.kernel,
            spec=spec,
            title=input.title,
        )
        data_uri = "data:image/gif;base64," + base64.b64encode(gif).decode("ascii")
        return ViewAnimationOutput(
            path=str(Path(output)),
            frames=input.frames,
            size_bytes=len(gif),
            data_uri=data_uri,
            status="success",
            message=f"Rendered {input.frames}-frame GIF ({len(gif)} bytes)",
        )
    except CADError as exc:
        return ViewAnimationOutput(
            path="",
            frames=0,
            size_bytes=0,
            data_uri="",
            status="error",
            message=str(exc),
        )


def cad_webgl_sync(input: WebGLSyncInput) -> WebGLSyncOutput:
    """Return an incremental WebGL synchronization delta.

    返回 WebGL 增量同步数据：对比客户端已持有的对象 id，产出新增/删除/
    更新的对象清单，供浏览器端增量更新场景。
    """
    try:
        doc = _doc()
        records = doc.entities.list()
        delta = export_webgl_delta(
            input.previous_ids,
            records,
            kernel=doc.entities.kernel,
            include_full=input.include_full,
        )
        full_uri = ""
        if input.include_full and delta.get("full"):
            import json

            payload = json.dumps(delta["full"]).encode("utf-8")
            full_uri = "data:application/json;base64," + base64.b64encode(payload).decode("ascii")
        return WebGLSyncOutput(
            added=delta["added"],
            removed=delta["removed"],
            updated=delta["updated"],
            object_count=delta["objectCount"],
            has_full=bool(full_uri),
            full_data_uri=full_uri,
            status="success",
            message=(
                f"{len(delta['added'])} added, {len(delta['removed'])} removed, "
                f"{len(delta['updated'])} updated"
            ),
        )
    except CADError as exc:
        return WebGLSyncOutput(
            object_count=0,
            status="error",
            message=str(exc),
        )


TOOLS: list[tuple[str, Any]] = [
    ("cad_view_3d_create", cad_view_3d_create),
    ("cad_view_3d_read", cad_view_3d_read),
    ("cad_view_3d_list", cad_view_3d_list),
    ("cad_view_3d_update", cad_view_3d_update),
    ("cad_view_3d_delete", cad_view_3d_delete),
    ("cad_view_3d_render", cad_view_3d_render),
    ("cad_view_section", cad_view_section),
    ("cad_view_explode", cad_view_explode),
    ("cad_view_animation", cad_view_animation),
    ("cad_webgl_sync", cad_webgl_sync),
]
