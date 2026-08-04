"""MCP drawing tool tests."""

from __future__ import annotations

from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from tianshangcad.mcp.tools.drawing import (
    DrawingAddDimensionInput,
    DrawingAddSectionInput,
    DrawingAddToleranceInput,
    DrawingAddViewInput,
    DrawingCreateInput,
    DrawingExportInput,
    cad_drawing_add_dimension,
    cad_drawing_add_section,
    cad_drawing_add_tolerance,
    cad_drawing_add_view,
    cad_drawing_create,
    cad_drawing_export,
)


class TestDrawingTools:
    """`cad_drawing_*` tool tests."""

    def _setup(self) -> str:
        cad_file_create(FileCreateInput(filename="drawing.json"))
        cad_drawing_create(DrawingCreateInput(name="engine", paper="A3", title="Reducer"))
        line = cad_object_create(
            ObjectCreateInput(
                type="line", params={"start": [0, 0, 0], "end": [100, 0, 0]}, layer="0"
            )
        ).object_id
        return line

    def test_create(self) -> None:
        cad_file_create(FileCreateInput(filename="a.json"))
        result = cad_drawing_create(DrawingCreateInput(name="engine", paper="A2"))
        assert result.status == "success"
        assert result.paper == "A2"
        assert result.width == 594.0

    def test_create_invalid_paper(self) -> None:
        cad_file_create(FileCreateInput(filename="a.json"))
        result = cad_drawing_create(DrawingCreateInput(name="engine", paper="XXL"))
        assert result.status == "error"

    def test_create_no_document(self) -> None:
        from tianshangcad.core.session import SessionManager

        SessionManager().reset()
        result = cad_drawing_create(DrawingCreateInput(name="engine"))
        assert result.status == "error"

    def test_add_view(self) -> None:
        line = self._setup()
        result = cad_drawing_add_view(
            DrawingAddViewInput(
                name="main", view_type="main", entity_ids=[line]
            )
        )
        assert result.status == "success"
        assert result.view_id != ""

    def test_add_view_invalid_type(self) -> None:
        self._setup()
        result = cad_drawing_add_view(
            DrawingAddViewInput(name="x", view_type="bogus")
        )
        assert result.status == "error"

    def test_add_section(self) -> None:
        self._setup()
        result = cad_drawing_add_section(
            DrawingAddSectionInput(name="sec", plane="XY", offset=5.0)
        )
        assert result.status == "success"
        assert result.view_id != ""

    def test_add_dimension(self) -> None:
        self._setup()
        result = cad_drawing_add_dimension(
            DrawingAddDimensionInput(dim_type="linear", value=42.5, position=[10, 10])
        )
        assert result.status == "success"
        assert result.dimension_id != ""
        assert result.value == 42.5

    def test_add_dimension_invalid_type(self) -> None:
        self._setup()
        result = cad_drawing_add_dimension(
            DrawingAddDimensionInput(dim_type="bogus", value=1.0)
        )
        assert result.status == "error"

    def test_add_tolerance(self) -> None:
        self._setup()
        result = cad_drawing_add_tolerance(
            DrawingAddToleranceInput(symbol="flatness", value=0.05, datum="A")
        )
        assert result.status == "success"
        assert result.label == "flatness 0.05 [A]"

    def test_add_tolerance_invalid_symbol(self) -> None:
        self._setup()
        result = cad_drawing_add_tolerance(DrawingAddToleranceInput(symbol="bogus"))
        assert result.status == "error"

    def test_export_svg(self, tmp_path) -> None:
        line = self._setup()
        cad_drawing_add_view(
            DrawingAddViewInput(name="main", view_type="main", entity_ids=[line])
        )
        out = tmp_path / "sheet.svg"
        result = cad_drawing_export(DrawingExportInput(format="svg", path=str(out)))
        assert result.status == "success"
        assert out.exists()

    def test_export_unsupported_format(self) -> None:
        self._setup()
        result = cad_drawing_export(
            DrawingExportInput(format="bmp", path="sheet.bmp")
        )
        assert result.status == "error"

    def test_export_empty_drawing(self, tmp_path) -> None:
        cad_file_create(FileCreateInput(filename="a.json"))
        cad_drawing_create(DrawingCreateInput(name="empty"))
        out = tmp_path / "sheet.svg"
        result = cad_drawing_export(DrawingExportInput(format="svg", path=str(out)))
        assert result.status == "success"
        assert out.exists()
