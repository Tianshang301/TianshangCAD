"""Engineering drawings (Phase 7 Task B).

A ``DrawingDocument`` turns document geometry into a formal 2D engineering
sheet: an ISO 216 paper (A0-A4) with a frame and title block, a set of
views (main / projection / section / detail / isometric), ISO 129-1
dimensions and GD&T annotations. The sheet can be exported to SVG (pure
Python), DXF (ezdxf) or PDF (matplotlib Agg).

Views reference document entities by id; :meth:`DrawingDocument.project`
produces 2D primitives per view. Dimensions store a value plus anchor
points so the value is explicit and deterministic; GD&T records attach a
symbol, value and datum to a referenced feature.

No optional dependency is required (``pip install -e .``).
"""

from __future__ import annotations

import enum
import math
import uuid
from typing import Any

from tianshangcad.core.kernel import CADKernel, get_kernel
from tianshangcad.render.renderer_2d import project_point
from tianshangcad.utils.errors import CADExportError, DrawingError

_PAPER_DIMS_MM: dict[str, tuple[float, float]] = {
    "A0": (1189.0, 841.0),
    "A1": (841.0, 594.0),
    "A2": (594.0, 420.0),
    "A3": (420.0, 297.0),
    "A4": (297.0, 210.0),
}

#: ISO 129-1 dimension kinds.
_DIMENSIONS_ISO = ("linear", "angular", "radial", "diameter", "ordinate")

#: GD&T feature-control symbols.
_GDT_SYMBOLS = ("position", "flatness", "parallelism", "perpendicularity", "concentricity")


def new_drawing_id(prefix: str = "dw") -> str:
    """Generate a unique drawing id."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def new_view_id(prefix: str = "vw") -> str:
    """Generate a unique view id."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def new_dimension_id(prefix: str = "dim") -> str:
    """Generate a unique dimension id."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def new_gdt_id(prefix: str = "gdt") -> str:
    """Generate a unique GD&T id."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class ViewType(enum.StrEnum):
    """Supported engineering view kinds."""

    MAIN = "main"
    PROJECTION = "projection"
    SECTION = "section"
    DETAIL = "detail"
    ISOMETRIC = "isometric"


class DimensionType(enum.StrEnum):
    """ISO 129-1 dimension kinds."""

    LINEAR = "linear"
    ANGULAR = "angular"
    RADIAL = "radial"
    DIAMETER = "diameter"
    ORDINATE = "ordinate"


class GdtSymbol(enum.StrEnum):
    """GD&T feature-control symbols."""

    POSITION = "position"
    FLATNESS = "flatness"
    PARALLELISM = "parallelism"
    PERPENDICULARITY = "perpendicularity"
    CONCENTRICITY = "concentricity"


def paper_size(name: str) -> tuple[float, float]:
    """Return the ``(width_mm, height_mm)`` of a paper name (A0-A4)."""
    key = str(name).upper()
    try:
        return _PAPER_DIMS_MM[key]
    except KeyError as exc:
        raise DrawingError(
            f"Unsupported paper size {name!r}; expected A0..A4",
            code="invalid_paper",
        ) from exc


class DrawingView:
    """A single view on a drawing sheet."""

    def __init__(
        self,
        view_id: str,
        name: str,
        view_type: str,
        scale: float = 1.0,
        translation: list[float] | None = None,
        direction: str = "front",
        entity_ids: list[str] | None = None,
        section_plane: str | None = None,
        section_offset: float | None = None,
        detail_center: list[float] | None = None,
        detail_scale: float = 2.0,
    ) -> None:
        """Initialize a drawing view."""
        try:
            self.type = ViewType(view_type.lower())
        except ValueError as exc:
            supported = ", ".join(v.value for v in ViewType)
            raise DrawingError(
                f"Unsupported view type {view_type!r}. Supported: {supported}",
                code="invalid_view_type",
            ) from exc
        self.id = view_id
        self.name = name
        self.scale = float(scale)
        self.translation: list[float] = list(translation or [0.0, 0.0])
        self.direction = direction  # main/projection/section use ortho directions
        self.entity_ids: list[str] = list(entity_ids or [])
        self.section_plane = section_plane
        self.section_offset = section_offset
        self.detail_center: list[float] = list(detail_center or [0.0, 0.0])
        self.detail_scale = float(detail_scale)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the view to a JSON-safe dict."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "scale": self.scale,
            "translation": list(self.translation),
            "direction": self.direction,
            "entity_ids": list(self.entity_ids),
            "section_plane": self.section_plane,
            "section_offset": self.section_offset,
            "detail_center": list(self.detail_center),
            "detail_scale": self.detail_scale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DrawingView:
        """Reconstruct a view from a serialized dict."""
        return cls(
            view_id=str(data["id"]),
            name=str(data["name"]),
            view_type=str(data["type"]),
            scale=float(data.get("scale", 1.0)),
            translation=data.get("translation"),
            direction=str(data.get("direction", "front")),
            entity_ids=data.get("entity_ids"),
            section_plane=data.get("section_plane"),
            section_offset=data.get("section_offset"),
            detail_center=data.get("detail_center"),
            detail_scale=float(data.get("detail_scale", 2.0)),
        )


class DrawingDimension:
    """An ISO 129-1 dimension annotation."""

    def __init__(
        self,
        dim_id: str,
        dim_type: str,
        value: float,
        points: list[list[float]] | None = None,
        position: list[float] | None = None,
        reference: str | None = None,
        text: str | None = None,
    ) -> None:
        """Initialize an ISO 129-1 dimension annotation."""
        try:
            self.type = DimensionType(dim_type.lower())
        except ValueError as exc:
            supported = ", ".join(d.value for d in DimensionType)
            raise DrawingError(
                f"Unsupported dimension type {dim_type!r}. Supported: {supported}",
                code="invalid_dimension",
            ) from exc
        self.id = dim_id
        self.value = float(value)
        self.points: list[list[float]] = [list(p) for p in (points or [])]
        self.position: list[float] = list(position or [0.0, 0.0])
        self.reference = reference
        self.text = text or f"{self.value:g}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the dimension to a JSON-safe dict."""
        return {
            "id": self.id,
            "type": self.type.value,
            "value": self.value,
            "points": [list(p) for p in self.points],
            "position": list(self.position),
            "reference": self.reference,
            "text": self.text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DrawingDimension:
        """Reconstruct a dimension from a serialized dict."""
        return cls(
            dim_id=str(data["id"]),
            dim_type=str(data["type"]),
            value=float(data["value"]),
            points=data.get("points"),
            position=data.get("position"),
            reference=data.get("reference"),
            text=data.get("text"),
        )


class DrawingGdt:
    """A GD&T feature-control frame."""

    def __init__(
        self,
        gdt_id: str,
        symbol: str,
        value: float | None = None,
        datum: str | None = None,
        reference: str | None = None,
        position: list[float] | None = None,
    ) -> None:
        """Initialize a GD&T feature-control frame."""
        try:
            self.symbol = GdtSymbol(symbol.lower())
        except ValueError as exc:
            supported = ", ".join(s.value for s in GdtSymbol)
            raise DrawingError(
                f"Unsupported GD&T symbol {symbol!r}. Supported: {supported}",
                code="invalid_gdt",
            ) from exc
        self.id = gdt_id
        self.value = None if value is None else float(value)
        self.datum = datum
        self.reference = reference
        self.position: list[float] = list(position or [0.0, 0.0])

    @property
    def label(self) -> str:
        """Return the formatted feature-control label text."""
        parts = [self.symbol.value]
        if self.value is not None:
            parts.append(f"{self.value:g}")
        if self.datum:
            parts.append(f"[{self.datum}]")
        return " ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the GD&T frame to a JSON-safe dict."""
        return {
            "id": self.id,
            "symbol": self.symbol.value,
            "value": self.value,
            "datum": self.datum,
            "reference": self.reference,
            "position": list(self.position),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DrawingGdt:
        """Reconstruct a GD&T frame from a serialized dict."""
        return cls(
            gdt_id=str(data["id"]),
            symbol=str(data["symbol"]),
            value=data.get("value"),
            datum=data.get("datum"),
            reference=data.get("reference"),
            position=data.get("position"),
        )


class DrawingDocument:
    """A 2D engineering drawing sheet with views, dimensions and GD&T."""

    def __init__(
        self,
        name: str | None = None,
        paper: str = "A4",
        title: str = "",
        drawn_by: str = "",
        scale: float = 1.0,
    ) -> None:
        """Initialize a 2D engineering drawing sheet."""
        self.name = name or "drawing"
        self.paper = paper.upper()
        self.width, self.height = paper_size(self.paper)
        self.title = title or self.name
        self.drawn_by = drawn_by
        self.scale = float(scale)
        self._views: dict[str, DrawingView] = {}
        self._dimensions: dict[str, DrawingDimension] = {}
        self._gdt: dict[str, DrawingGdt] = {}

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def views(self) -> list[DrawingView]:
        """Return all views in insertion order."""
        return list(self._views.values())

    @property
    def dimensions(self) -> list[DrawingDimension]:
        """Return all dimensions in insertion order."""
        return list(self._dimensions.values())

    @property
    def tolerances(self) -> list[DrawingGdt]:
        """Return all GD&T frames in insertion order."""
        return list(self._gdt.values())

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def add_view(
        self,
        name: str,
        view_type: str,
        scale: float = 1.0,
        translation: list[float] | None = None,
        direction: str = "front",
        entity_ids: list[str] | None = None,
    ) -> str:
        """Add a view to the sheet, returning its view id."""
        view = DrawingView(
            new_view_id(),
            name,
            view_type,
            scale,
            translation,
            direction,
            entity_ids,
        )
        self._views[view.id] = view
        return view.id

    def add_section(
        self,
        name: str,
        entity_ids: list[str] | None = None,
        plane: str = "XZ",
        offset: float = 0.0,
        translation: list[float] | None = None,
    ) -> str:
        """Add a section view (a clipped orthographic projection)."""
        view = DrawingView(
            new_view_id(),
            name,
            ViewType.SECTION,
            scale=1.0,
            translation=translation,
            direction="front",
            entity_ids=entity_ids,
            section_plane=plane,
            section_offset=offset,
        )
        self._views[view.id] = view
        return view.id

    def add_dimension(
        self,
        dim_type: str,
        value: float,
        points: list[list[float]] | None = None,
        position: list[float] | None = None,
        reference: str | None = None,
    ) -> str:
        """Add an ISO 129-1 dimension, returning its dimension id."""
        dimension = DrawingDimension(
            new_dimension_id(), dim_type, value, points, position, reference
        )
        self._dimensions[dimension.id] = dimension
        return dimension.id

    def add_tolerance(
        self,
        symbol: str,
        value: float | None = None,
        datum: str | None = None,
        reference: str | None = None,
    ) -> str:
        """Add a GD&T feature-control frame, returning its id."""
        gdt = DrawingGdt(
            new_gdt_id(), symbol, value, datum, reference
        )
        self._gdt[gdt.id] = gdt
        return gdt.id

    def get_view(self, view_id: str) -> DrawingView:
        """Return a view or raise ``DrawingError``."""
        if view_id not in self._views:
            raise DrawingError(f"View not found: {view_id}", code="view_not_found")
        return self._views[view_id]

    def get_dimension(self, dim_id: str) -> DrawingDimension:
        """Return a dimension or raise ``DrawingError``."""
        if dim_id not in self._dimensions:
            raise DrawingError(
                f"Dimension not found: {dim_id}", code="dimension_not_found"
            )
        return self._dimensions[dim_id]

    def get_tolerance(self, gdt_id: str) -> DrawingGdt:
        """Return a GD&T frame or raise ``DrawingError``."""
        if gdt_id not in self._gdt:
            raise DrawingError(f"GD&T not found: {gdt_id}", code="gdt_not_found")
        return self._gdt[gdt_id]

    def remove_view(self, view_id: str) -> None:
        """Remove a view or raise ``DrawingError``."""
        if view_id not in self._views:
            raise DrawingError(f"View not found: {view_id}", code="view_not_found")
        del self._views[view_id]

    # ------------------------------------------------------------------
    # Projection
    # ------------------------------------------------------------------

    def _project_entity(
        self,
        view: DrawingView,
        record: Any,
        kernel: CADKernel,
    ) -> list[list[list[float]]]:
        """Project one entity into 2D view space.

        Returns a list of 2D polylines ``[[[x, y], ...], ...]``. Uses the
        orthographic projection from ``render.renderer_2d.project_point``
        scaled and translated into sheet coordinates.
        """
        shape = record.shape
        kind = shape["kind"]
        polylines: list[list[list[float]]] = []
        if kind == "line":
            start = shape["params"]["start"]
            end = shape["params"]["end"]
            polylines.append(
                [self._to_sheet(view, project_point(start, view.direction)),
                 self._to_sheet(view, project_point(end, view.direction))]
            )
        elif kind in ("circle", "arc"):
            center = shape["params"]["center"]
            cx, cy = project_point(center, view.direction)
            radius = float(shape["params"]["radius"]) * view.scale
            sheet_center = self._to_sheet(view, [cx, cy])
            # Approximate circles with 32-segment polylines for export.
            points: list[list[float]] = []
            for i in range(33):
                angle = 2.0 * math.pi * i / 32
                points.append(
                    [sheet_center[0] + radius * math.cos(angle),
                     sheet_center[1] + radius * math.sin(angle)]
                )
            polylines.append(points)
        else:
            vertices, faces = kernel.tessellate(shape)
            edges: set[tuple[int, int]] = set()
            for face in faces:
                n = len(face)
                for i in range(n):
                    a, b = face[i], face[(i + 1) % n]
                    key = (a, b) if a <= b else (b, a)
                    if key in edges:
                        continue
                    edges.add(key)
                    polylines.append(
                        [
                            self._to_sheet(view, project_point(vertices[a], view.direction)),
                            self._to_sheet(view, project_point(vertices[b], view.direction)),
                        ]
                    )
        return polylines

    def _to_sheet(
        self, view: DrawingView, projected: tuple[float, float] | list[float]
    ) -> list[float]:
        return [
            view.translation[0] + float(projected[0]) * view.scale,
            view.translation[1] + float(projected[1]) * view.scale,
        ]

    def project(
        self,
        records: dict[str, Any],
        kernel: CADKernel | None = None,
    ) -> dict[str, list[list[list[float]]]]:
        """Project every view's entities into 2D sheet coordinates.

        ``records`` maps entity ids to ``EntityRecord`` objects (from the
        document). Returns ``{view_id: [polylines]}``.
        """
        active_kernel = kernel or get_kernel()
        output: dict[str, list[list[list[float]]]] = {}
        for view in self._views.values():
            polylines: list[list[list[float]]] = []
            for entity_id in view.entity_ids:
                record = records.get(entity_id)
                if record is None:
                    continue
                polylines.extend(self._project_entity(view, record, active_kernel))
            output[view.id] = polylines
        return output

    # ------------------------------------------------------------------
    # Frame / title block
    # ------------------------------------------------------------------

    def frame(self, margin: float = 10.0) -> list[float]:
        """Return the frame rectangle as ``[x0, y0, x1, y1]`` in sheet mm."""
        return [margin, margin, self.width - margin, self.height - margin]

    def title_block(self) -> dict[str, Any]:
        """Return the title block rectangle and fields for the sheet."""
        margin = 10.0
        block_width = 180.0
        block_height = 50.0
        x0 = self.width - margin - block_width
        y0 = margin
        return {
            "rect": [x0, y0, x0 + block_width, y0 + block_height],
            "fields": {
                "title": self.title,
                "drawn_by": self.drawn_by,
                "paper": self.paper,
                "scale": f"1:{self.scale:g}",
            },
        }

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_svg(
        self,
        records: dict[str, Any],
        filepath: str,
        kernel: CADKernel | None = None,
    ) -> str:
        """Export the sheet to an SVG file, returning the written path."""
        projected = self.project(records, kernel)
        lines: list[str] = []
        lines.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width:g}" '
            f'height="{self.height:g}" viewBox="0 0 {self.width:g} {self.height:g}">'
        )
        lines.append(f'  <rect width="{self.width:g}" height="{self.height:g}" fill="white"/>')
        fx0, fy0, fx1, fy1 = self.frame()
        lines.append(
            f'  <rect x="{fx0:g}" y="{fy0:g}" width="{fx1 - fx0:g}" '
            f'height="{fy1 - fy0:g}" fill="none" stroke="black" stroke-width="0.6"/>'
        )
        for view_id, polylines in projected.items():
            lines.append(f'  <g id="{view_id}">')
            for polyline in polylines:
                coords = " ".join(f"{p[0]:g},{p[1]:g}" for p in polyline)
                lines.append(
                    f'    <polyline points="{coords}" fill="none" stroke="black" '
                    'stroke-width="0.3"/>'
                )
            lines.append("  </g>")
        for dimension in self._dimensions.values():
            lines.append(
                f'  <text x="{dimension.position[0]:g}" y="{dimension.position[1]:g}" '
                f'font-size="3" font-family="sans-serif">{dimension.text}</text>'
            )
        for gdt in self._gdt.values():
            lines.append(
                f'  <text x="{gdt.position[0]:g}" y="{gdt.position[1]:g}" '
                f'font-size="3" font-family="sans-serif">{gdt.label}</text>'
            )
        block = self.title_block()
        bx0, by0, bx1, by1 = block["rect"]
        lines.append(
            f'  <rect x="{bx0:g}" y="{by0:g}" width="{bx1 - bx0:g}" '
            f'height="{by1 - by0:g}" fill="none" stroke="black" stroke-width="0.6"/>'
        )
        for index, (key, value) in enumerate(block["fields"].items()):
            ty = by1 - 6.0 - index * 5.0
            lines.append(
                f'  <text x="{bx0 + 4:g}" y="{ty:g}" font-size="3" '
                f'font-family="sans-serif">{key}: {value}</text>'
            )
        lines.append("</svg>")
        svg = "\n".join(lines)
        with open(filepath, "w", encoding="utf-8") as target:
            target.write(svg)
        return filepath

    def export_dxf(
        self,
        records: dict[str, Any],
        filepath: str,
        kernel: CADKernel | None = None,
    ) -> str:
        """Export the sheet to a DXF file, returning the written path."""
        import ezdxf

        doc = ezdxf.new("R2010")  # type: ignore[attr-defined]
        msp = doc.modelspace()
        fx0, fy0, fx1, fy1 = self.frame()
        msp.add_lwpolyline(
            [(fx0, fy0), (fx1, fy0), (fx1, fy1), (fx0, fy1), (fx0, fy0)],
            close=True,
        )
        projected = self.project(records, kernel)
        for _view_id, polylines in projected.items():
            for polyline in polylines:
                points = [(p[0], p[1]) for p in polyline]
                msp.add_lwpolyline(points)
        for dimension in self._dimensions.values():
            msp.add_text(
                dimension.text,
                height=3.0,
                dxfattribs={"insert": (dimension.position[0], dimension.position[1])},
            )
        for gdt in self._gdt.values():
            msp.add_text(
                gdt.label,
                height=3.0,
                dxfattribs={"insert": (gdt.position[0], gdt.position[1])},
            )
        block = self.title_block()
        bx0, by0, bx1, by1 = block["rect"]
        msp.add_lwpolyline(
            [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1), (bx0, by0)], close=True
        )
        for index, (key, value) in enumerate(block["fields"].items()):
            msp.add_text(
                f"{key}: {value}",
                height=3.0,
                dxfattribs={"insert": (bx0 + 4, by1 - 6.0 - index * 5.0)},
            )
        try:
            doc.saveas(filepath)
        except OSError as exc:
            raise CADExportError(
                f"Failed to write DXF {filepath}: {exc}", code="write_failed"
            ) from exc
        return filepath

    def export_pdf(
        self,
        records: dict[str, Any],
        filepath: str,
        kernel: CADKernel | None = None,
    ) -> str:
        """Export the sheet to a PDF file (matplotlib Agg), returning the path."""
        import matplotlib

        matplotlib.use("Agg")

        from matplotlib import pyplot as plt
        from matplotlib.patches import Rectangle

        projected = self.project(records, kernel)
        fig, ax = plt.subplots(figsize=(self.width / 72.0, self.height / 72.0), dpi=72)
        ax.set_aspect("equal")
        ax.set_xlim(0, self.width)
        ax.set_ylim(0, self.height)
        ax.axis("off")
        fx0, fy0, fx1, fy1 = self.frame()
        ax.add_patch(
            Rectangle((fx0, fy0), fx1 - fx0, fy1 - fy0, fill=False, edgecolor="black")
        )
        for _view_id, polylines in projected.items():
            for polyline in polylines:
                xs = [p[0] for p in polyline]
                ys = [p[1] for p in polyline]
                ax.plot(xs, ys, color="black", linewidth=0.5)
        for dimension in self._dimensions.values():
            ax.text(
                dimension.position[0],
                dimension.position[1],
                dimension.text,
                fontsize=6,
            )
        for gdt in self._gdt.values():
            ax.text(gdt.position[0], gdt.position[1], gdt.label, fontsize=6)
        block = self.title_block()
        bx0, by0, bx1, by1 = block["rect"]
        ax.add_patch(
            Rectangle((bx0, by0), bx1 - bx0, by1 - by0, fill=False, edgecolor="black")
        )
        for index, (key, value) in enumerate(block["fields"].items()):
            ax.text(bx0 + 4, by1 - 6.0 - index * 5.0, f"{key}: {value}", fontsize=6)
        fig.savefig(filepath, format="pdf")
        plt.close(fig)
        return filepath

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize the drawing to a JSON-safe dict."""
        return {
            "name": self.name,
            "paper": self.paper,
            "title": self.title,
            "drawn_by": self.drawn_by,
            "scale": self.scale,
            "views": [view.to_dict() for view in self._views.values()],
            "dimensions": [dim.to_dict() for dim in self._dimensions.values()],
            "tolerances": [gdt.to_dict() for gdt in self._gdt.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DrawingDocument:
        """Reconstruct a drawing from a serialized dict."""
        doc = cls(
            name=str(data.get("name", "drawing")),
            paper=str(data.get("paper", "A4")),
            title=str(data.get("title", "")),
            drawn_by=str(data.get("drawn_by", "")),
            scale=float(data.get("scale", 1.0)),
        )
        for view_data in data.get("views", []):
            view = DrawingView.from_dict(view_data)
            doc._views[view.id] = view
        for dim_data in data.get("dimensions", []):
            dim = DrawingDimension.from_dict(dim_data)
            doc._dimensions[dim.id] = dim
        for gdt_data in data.get("tolerances", []):
            gdt = DrawingGdt.from_dict(gdt_data)
            doc._gdt[gdt.id] = gdt
        return doc
