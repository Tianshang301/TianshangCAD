"""Engineering drawing unit tests."""

from __future__ import annotations

import math

import pytest

from cad_mcp_server.core.drawing import (
    DimensionType,
    DrawingDimension,
    DrawingDocument,
    DrawingGdt,
    DrawingView,
    GdtSymbol,
    ViewType,
    paper_size,
)
from cad_mcp_server.core.entity import EntityManager
from cad_mcp_server.utils.errors import DrawingError


class TestPaper:
    """Paper size selection."""

    def test_paper_sizes(self) -> None:
        assert paper_size("A4") == (297.0, 210.0)
        assert paper_size("A0") == (1189.0, 841.0)
        assert paper_size("A3") == (420.0, 297.0)

    def test_paper_accepts_lowercase(self) -> None:
        assert paper_size("a4") == (297.0, 210.0)

    def test_invalid_paper(self) -> None:
        with pytest.raises(DrawingError):
            paper_size("XXL")


class TestView:
    """View construction and types."""

    def test_view_types(self) -> None:
        values = [v.value for v in ViewType]
        assert values == ["main", "projection", "section", "detail", "isometric"]

    def test_add_view(self) -> None:
        doc = DrawingDocument()
        view_id = doc.add_view("main", "main", scale=2.0, translation=[10, 10])
        view = doc.get_view(view_id)
        assert view.type == ViewType.MAIN
        assert view.scale == 2.0
        assert view.translation == [10, 10]

    def test_invalid_view_type(self) -> None:
        with pytest.raises(DrawingError):
            DrawingDocument().add_view("x", "bogus")

    def test_remove_view(self) -> None:
        doc = DrawingDocument()
        view_id = doc.add_view("main", "main")
        doc.remove_view(view_id)
        assert len(doc.views) == 0
        with pytest.raises(DrawingError):
            doc.get_view(view_id)

    def test_section_view(self) -> None:
        doc = DrawingDocument()
        view_id = doc.add_section("sec", plane="XY", offset=5.0)
        view = doc.get_view(view_id)
        assert view.type == ViewType.SECTION
        assert view.section_plane == "XY"
        assert view.section_offset == 5.0


class TestDimension:
    """Dimension construction."""

    def test_dimension_types(self) -> None:
        values = [d.value for d in DimensionType]
        assert values == ["linear", "angular", "radial", "diameter", "ordinate"]

    def test_add_dimension(self) -> None:
        doc = DrawingDocument()
        dim_id = doc.add_dimension("linear", 42.5, position=[10, 10])
        dim = doc.get_dimension(dim_id)
        assert dim.type == DimensionType.LINEAR
        assert dim.value == 42.5
        assert dim.text == "42.5"

    def test_invalid_dimension_type(self) -> None:
        with pytest.raises(DrawingError):
            DrawingDocument().add_dimension("bogus", 1.0)

    def test_custom_text(self) -> None:
        dim = DrawingDimension("d1", "radial", 25.0, text="R25")
        assert dim.text == "R25"


class TestGdt:
    """GD&T feature-control frames."""

    def test_gdt_symbols(self) -> None:
        values = [g.value for g in GdtSymbol]
        assert values == [
            "position",
            "flatness",
            "parallelism",
            "perpendicularity",
            "concentricity",
        ]

    def test_add_tolerance(self) -> None:
        doc = DrawingDocument()
        gdt_id = doc.add_tolerance("flatness", value=0.05, datum="A")
        gdt = doc.get_tolerance(gdt_id)
        assert gdt.symbol == GdtSymbol.FLATNESS
        assert gdt.label == "flatness 0.05 [A]"

    def test_invalid_symbol(self) -> None:
        with pytest.raises(DrawingError):
            DrawingDocument().add_tolerance("bogus")

    def test_label_without_value(self) -> None:
        gdt = DrawingGdt("g1", "position")
        assert gdt.label == "position"


class TestProjection:
    """View projection correctness."""

    def _records(self) -> tuple[EntityManager, dict, list[str]]:
        em = EntityManager()
        line = em.create("line", {"start": [0, 0, 0], "end": [100, 0, 0]})
        circle = em.create("circle", {"center": [50, 50, 0], "radius": 10})
        return em, {line: em.get(line), circle: em.get(circle)}, [line, circle]

    def test_line_projection_front(self) -> None:
        _, records, ids = self._records()
        doc = DrawingDocument()
        view_id = doc.add_view(
            "main", "main", translation=[20, 30], direction="front", entity_ids=ids
        )
        projected = doc.project(records)[view_id]
        line_poly = projected[0]
        # front view projects (x, z); line is along x at z=0, translated by [20,30].
        assert line_poly[0] == [20.0, 30.0]
        assert line_poly[1] == [120.0, 30.0]

    def test_line_projection_scaled(self) -> None:
        _, records, ids = self._records()
        doc = DrawingDocument()
        view_id = doc.add_view("main", "main", scale=2.0, translation=[0, 0], entity_ids=ids)
        projected = doc.project(records)[view_id]
        assert projected[0][1] == [200.0, 0.0]

    def test_circle_projection(self) -> None:
        _, records, ids = self._records()
        doc = DrawingDocument()
        view_id = doc.add_view("main", "main", entity_ids=ids)
        projected = doc.project(records)[view_id]
        # front view projects (x, z): circle center (50,50,0) -> (50, 0), radius 10.
        circle_poly = projected[1]
        assert len(circle_poly) == 33
        first = circle_poly[0]
        cx, cy = (50.0, 0.0)
        assert math.isclose(first[0] - cx, 10.0, abs_tol=1e-6)
        assert math.isclose(first[1] - cy, 0.0, abs_tol=1e-6)

    def test_view_without_entities_is_empty(self) -> None:
        doc = DrawingDocument()
        view_id = doc.add_view("main", "main")
        assert doc.project({})[view_id] == []

    def test_missing_entity_skipped(self) -> None:
        doc = DrawingDocument()
        view_id = doc.add_view("main", "main", entity_ids=["nope"])
        assert doc.project({})[view_id] == []


class TestFrameTitle:
    """Frame and title block."""

    def test_frame(self) -> None:
        doc = DrawingDocument(paper="A4")
        assert doc.frame() == [10.0, 10.0, 287.0, 200.0]

    def test_title_block_fields(self) -> None:
        doc = DrawingDocument(paper="A3", title="Reducer", drawn_by="Tianshang")
        block = doc.title_block()
        assert block["fields"]["title"] == "Reducer"
        assert block["fields"]["drawn_by"] == "Tianshang"
        assert block["fields"]["paper"] == "A3"
        assert block["fields"]["scale"] == "1:1"


class TestSerialization:
    """to_dict/from_dict round-trips."""

    def test_roundtrip_full(self) -> None:
        doc = DrawingDocument(paper="A2", title="Engine")
        doc.add_view("main", "main", entity_ids=["e1"])
        doc.add_section("sec", plane="XZ", offset=2.0)
        doc.add_dimension("linear", 10.0, position=[1, 2])
        doc.add_tolerance("parallelism", 0.01, datum="B")
        restored = DrawingDocument.from_dict(doc.to_dict())
        assert restored.paper == "A2"
        assert len(restored.views) == 2
        assert len(restored.dimensions) == 1
        assert len(restored.tolerances) == 1

    def test_view_roundtrip(self) -> None:
        view = DrawingView("v1", "main", "detail", scale=3.0, detail_center=[5, 5])
        restored = DrawingView.from_dict(view.to_dict())
        assert restored.type == ViewType.DETAIL
        assert restored.detail_center == [5, 5]

    def test_dimension_roundtrip(self) -> None:
        dim = DrawingDimension("d1", "ordinate", 7.5, points=[[1, 2]])
        restored = DrawingDimension.from_dict(dim.to_dict())
        assert restored.value == 7.5
        assert restored.points == [[1, 2]]


class TestExport:
    """Export file-header checks."""

    def _records(self) -> tuple[dict, list[str]]:
        em = EntityManager()
        line = em.create("line", {"start": [0, 0, 0], "end": [100, 0, 0]})
        return {line: em.get(line)}, [line]

    def test_export_svg(self, tmp_path) -> None:
        records, ids = self._records()
        doc = DrawingDocument(paper="A4")
        doc.add_view("main", "main", entity_ids=ids)
        out = tmp_path / "sheet.svg"
        doc.export_svg(records, str(out))
        head = out.read_text(encoding="utf-8")
        assert head.strip().startswith('<svg xmlns="http://www.w3.org/2000/svg"')
        assert "polyline" in head
        assert "title: " in head

    def test_export_dxf(self, tmp_path) -> None:
        records, ids = self._records()
        doc = DrawingDocument(paper="A3")
        doc.add_view("main", "main", entity_ids=ids)
        out = tmp_path / "sheet.dxf"
        doc.export_dxf(records, str(out))
        assert out.exists()
        assert out.stat().st_size > 0

    def test_export_pdf(self, tmp_path) -> None:
        records, ids = self._records()
        doc = DrawingDocument(paper="A4")
        doc.add_view("main", "main", entity_ids=ids)
        out = tmp_path / "sheet.pdf"
        doc.export_pdf(records, str(out))
        assert out.exists()
        with open(out, "rb") as handle:
            assert handle.read(5) == b"%PDF-"
