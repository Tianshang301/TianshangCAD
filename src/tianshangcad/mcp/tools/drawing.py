"""Engineering drawing tools: create sheet, add views/sections, dimensions, GD&T and export."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.core.drawing import DrawingDocument
from tianshangcad.utils.errors import CADError, DrawingError


class DrawingCreateInput(BaseModel):
    """Input for creating a drawing sheet."""

    name: str = Field("drawing", description="Drawing name")
    paper: str = Field("A4", description="Paper size: A0, A1, A2, A3, A4")
    title: str = Field("", description="Title block title")
    drawn_by: str = Field("", description="Title block author")


class DrawingCreateOutput(BaseModel):
    """Output for creating a drawing."""

    drawing_id: str = Field(..., description="Drawing identifier")
    paper: str = Field(..., description="Paper size")
    width: float = Field(..., description="Sheet width in mm")
    height: float = Field(..., description="Sheet height in mm")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class DrawingAddViewInput(BaseModel):
    """Input for adding a view."""

    name: str = Field(..., description="View name")
    view_type: str = Field(
        ...,
        description="main, projection, section, detail or isometric",
    )
    scale: float = Field(1.0, description="View scale factor", gt=0)
    translation: list[float] | None = Field(None, description="Sheet offset [x, y]")
    direction: str = Field("front", description="Orthographic direction: top/front/side")
    entity_ids: list[str] | None = Field(None, description="Referenced document entity ids")


class DrawingAddViewOutput(BaseModel):
    """Output for adding a view."""

    view_id: str = Field(..., description="View identifier")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class DrawingAddSectionInput(BaseModel):
    """Input for adding a section view."""

    name: str = Field(..., description="Section view name")
    entity_ids: list[str] | None = Field(None, description="Referenced entity ids")
    plane: str = Field("XZ", description="Section plane: XY, YZ or XZ")
    offset: float = Field(0.0, description="Plane offset along the normal")
    translation: list[float] | None = Field(None, description="Sheet offset [x, y]")


class DrawingAddSectionOutput(BaseModel):
    """Output for adding a section view."""

    view_id: str = Field(..., description="Section view identifier")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class DrawingAddDimensionInput(BaseModel):
    """Input for adding a dimension."""

    dim_type: str = Field(
        ..., description="linear, angular, radial, diameter or ordinate (ISO 129-1)"
    )
    value: float = Field(..., description="Dimension value")
    points: list[list[float]] | None = Field(None, description="Anchor points [[x, y], ...]")
    position: list[float] | None = Field(None, description="Text position [x, y]")
    reference: str | None = Field(None, description="Referenced entity or view id")


class DrawingAddDimensionOutput(BaseModel):
    """Output for adding a dimension."""

    dimension_id: str = Field(..., description="Dimension identifier")
    dim_type: str = Field(..., description="Dimension type")
    value: float = Field(..., description="Dimension value")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class DrawingAddToleranceInput(BaseModel):
    """Input for adding a GD&T feature-control frame."""

    symbol: str = Field(
        ...,
        description="position, flatness, parallelism, perpendicularity or concentricity",
    )
    value: float | None = Field(None, description="Tolerance value")
    datum: str | None = Field(None, description="Datum reference, e.g. 'A'")
    reference: str | None = Field(None, description="Referenced entity or view id")


class DrawingAddToleranceOutput(BaseModel):
    """Output for adding GD&T."""

    tolerance_id: str = Field(..., description="GD&T identifier")
    symbol: str = Field(..., description="GD&T symbol")
    label: str = Field(..., description="Formatted feature-control label")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class DrawingExportInput(BaseModel):
    """Input for exporting a drawing."""

    format: str = Field(..., description="Export format: svg, dxf or pdf")
    path: str = Field(..., description="Target file path")


class DrawingExportOutput(BaseModel):
    """Output for exporting a drawing."""

    path: str = Field(..., description="Written file path")
    format: str = Field(..., description="Exported format")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _require_drawing() -> DrawingDocument:
    return DocumentManager().get_current().drawing()


def _records_from_document() -> dict[str, Any]:
    doc = DocumentManager().get_current()
    return {record.id: record for record in doc.entities.list()}


def cad_drawing_create(input: DrawingCreateInput) -> DrawingCreateOutput:
    """Create an engineering drawing sheet in the current document.

    Creates (or returns the existing) A0–A4 sheet with a frame and title
    block. Views, dimensions and GD&T are added afterwards.
    """
    try:
        doc = DocumentManager().get_current()
        drawing = doc.drawing(paper=input.paper, title=input.title)
        drawing.name = input.name
        drawing.drawn_by = input.drawn_by
        return DrawingCreateOutput(
            drawing_id=drawing.name,
            paper=drawing.paper,
            width=drawing.width,
            height=drawing.height,
            status="success",
            message=f"Drawing {drawing.name} ready ({drawing.paper})",
        )
    except CADError as exc:
        return DrawingCreateOutput(
            drawing_id="", paper=input.paper, width=0.0, height=0.0,
            status="error", message=str(exc),
        )


class DrawingDeleteInput(BaseModel):
    """Input for deleting the current drawing sheet."""

    confirm: bool = Field(True, description="Set to true to confirm deletion")


class DrawingDeleteOutput(BaseModel):
    """Output for deleting a drawing."""

    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


def cad_drawing_delete(input: DrawingDeleteInput) -> DrawingDeleteOutput:
    """Delete the current drawing sheet from the document.

    删除当前文档中的工程图。视图、尺寸与 GD&T 一并丢弃，不可撤销。
    """
    try:
        if not input.confirm:
            raise DrawingError("Deletion requires confirm=true", code="not_confirmed")
        doc = DocumentManager().get_current()
        doc.reset_drawing()
        return DrawingDeleteOutput(status="success", message="Drawing deleted")
    except CADError as exc:
        return DrawingDeleteOutput(status="error", message=str(exc))


def cad_drawing_add_view(input: DrawingAddViewInput) -> DrawingAddViewOutput:
    """Add a view (main/projection/section/detail/isometric) to the sheet.

    添加工程图视图。``view_type`` 为 main/projection/section/detail/
    isometric；可选 ``scale``、``translation``、``direction`` 控制布局。
    Views reference the document geometry via ``entity_ids``.

    When not to use: for a clipping plane view use ``cad_drawing_add_section``
    (not ``view_type=section``) and for ISO dimensions use
    ``cad_drawing_add_dimension``. A sheet must exist first
    (``cad_drawing_create``).
    """
    try:
        drawing = _require_drawing()
        view_id = drawing.add_view(
            name=input.name,
            view_type=input.view_type,
            scale=input.scale,
            translation=input.translation,
            direction=input.direction,
            entity_ids=input.entity_ids,
        )
        return DrawingAddViewOutput(
            view_id=view_id, status="success", message=f"Added {input.view_type} view"
        )
    except DrawingError as exc:
        return DrawingAddViewOutput(view_id="", status="error", message=str(exc))


def cad_drawing_add_section(input: DrawingAddSectionInput) -> DrawingAddSectionOutput:
    """Add a section view clipped by a plane (XY / YZ / XZ).

    添加剖视图。``plane`` 为 XY/YZ/XZ，``offset`` 沿法向偏移切割面，
    ``entity_ids`` 限定参与剖切的几何。Generates a section view on the sheet.

    When not to use: for a plain unscaled projection use
    ``cad_drawing_add_view`` (``view_type=main/projection``); sections are
    only for clipped, plane-cut views. Requires an existing sheet.
    """
    try:
        drawing = _require_drawing()
        view_id = drawing.add_section(
            name=input.name,
            entity_ids=input.entity_ids,
            plane=input.plane,
            offset=input.offset,
            translation=input.translation,
        )
        return DrawingAddSectionOutput(
            view_id=view_id, status="success", message=f"Added section view {input.name}"
        )
    except DrawingError as exc:
        return DrawingAddSectionOutput(view_id="", status="error", message=str(exc))


def cad_drawing_add_dimension(input: DrawingAddDimensionInput) -> DrawingAddDimensionOutput:
    """Add an ISO 129-1 dimension to the drawing.

    ``dim_type`` is one of linear, angular, radial, diameter or ordinate.
    ``value`` is the nominal dimension value; ``points`` optionally anchor
    it to geometry.

    When not to use: for tolerance annotations use
    ``cad_drawing_add_tolerance`` (GD&T), not a dimension. Dimensions need
    an existing view on the sheet.
    """
    try:
        drawing = _require_drawing()
        dim_id = drawing.add_dimension(
            dim_type=input.dim_type,
            value=input.value,
            points=input.points,
            position=input.position,
            reference=input.reference,
        )
        dimension = drawing.get_dimension(dim_id)
        return DrawingAddDimensionOutput(
            dimension_id=dim_id,
            dim_type=dimension.type.value,
            value=dimension.value,
            status="success",
            message=f"Added {input.dim_type} dimension {dimension.value:g}",
        )
    except DrawingError as exc:
        return DrawingAddDimensionOutput(
            dimension_id="", dim_type=input.dim_type, value=input.value,
            status="error", message=str(exc),
        )


def cad_drawing_add_tolerance(input: DrawingAddToleranceInput) -> DrawingAddToleranceOutput:
    """Add a GD&T feature-control frame to the drawing.

    添加 GD&T 形位公差框。``symbol`` 为 position/flatness/parallelism/
    perpendicularity/concentricity 等，可配 ``value`` 与基准 ``datum``。

    When not to use: for plain size dimensions (no tolerance) use
    ``cad_drawing_add_dimension``. GD&T frames annotate a referenced
    feature; without a reference the frame is placed at ``position``.
    """
    try:
        drawing = _require_drawing()
        gdt_id = drawing.add_tolerance(
            symbol=input.symbol,
            value=input.value,
            datum=input.datum,
            reference=input.reference,
        )
        gdt = drawing.get_tolerance(gdt_id)
        return DrawingAddToleranceOutput(
            tolerance_id=gdt_id,
            symbol=gdt.symbol.value,
            label=gdt.label,
            status="success",
            message=f"Added {gdt.label}",
        )
    except DrawingError as exc:
        return DrawingAddToleranceOutput(
            tolerance_id="", symbol=input.symbol, label="", status="error", message=str(exc)
        )


def cad_drawing_export(input: DrawingExportInput) -> DrawingExportOutput:
    """Export the drawing to an SVG, DXF or PDF file.

    导出工程图。``format`` 为 svg（矢量）、dxf（CAD 交换）或 pdf（打印）。
    Exports the current sheet with its views, dimensions and GD&T frames.

    When not to use: to share geometry rather than a drawing sheet use
    ``cad_file_io`` (export step/dxf) or ``cad_render``. Requires an
    existing drawing with at least one view.
    """
    try:
        drawing = _require_drawing()
        records = _records_from_document()
        kernel = DocumentManager().get_current().entities.kernel
        fmt = input.format.lower()
        if fmt == "svg":
            drawing.export_svg(records, input.path, kernel)
        elif fmt == "dxf":
            drawing.export_dxf(records, input.path, kernel)
        elif fmt == "pdf":
            drawing.export_pdf(records, input.path, kernel)
        else:
            return DrawingExportOutput(
                path="", format=input.format, status="error",
                message=f"Unsupported export format: {input.format}",
            )
        return DrawingExportOutput(
            path=input.path, format=fmt, status="success", message="Exported"
        )
    except CADError as exc:
        return DrawingExportOutput(
            path="", format=input.format, status="error", message=str(exc)
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_drawing_create", cad_drawing_create),
    ("cad_drawing_add_view", cad_drawing_add_view),
    ("cad_drawing_add_section", cad_drawing_add_section),
    ("cad_drawing_add_dimension", cad_drawing_add_dimension),
    ("cad_drawing_add_tolerance", cad_drawing_add_tolerance),
    ("cad_drawing_delete", cad_drawing_delete),
    ("cad_drawing_export", cad_drawing_export),
]
