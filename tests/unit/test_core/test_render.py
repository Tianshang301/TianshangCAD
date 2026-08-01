"""Tests for the 2D / 3D rendering and WebGL export engines."""

from __future__ import annotations

from cad_mcp_server.core.kernel import AnalyticKernel
from cad_mcp_server.render.renderer_2d import render_view
from cad_mcp_server.render.renderer_3d import render_3d
from cad_mcp_server.render.webgl_exporter import (
    export_webgl,
    export_webgl_file,
    viewer_html,
)
from cad_mcp_server.utils.errors import CADValidationError

_KERNEL = AnalyticKernel()

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class _Record:
    def __init__(self, shape) -> None:
        self.shape = shape
        self.id = "obj"


def _records() -> list[_Record]:
    return [
        _Record(_KERNEL.create_box([0, 0, 0], [10, 5, 2])),
        _Record(_KERNEL.create_circle([3, 3, 0], 2)),
        _Record(_KERNEL.create_line([0, 0, 0], [5, 5, 5])),
    ]


class TestRenderer2D:
    """2D orthographic PNG rendering."""

    def test_render_top_png(self) -> None:
        png = render_view(_records(), view="top", dpi=96, kernel=_KERNEL)
        assert png.startswith(_PNG_MAGIC)
        assert len(png) > 1000

    def test_all_views_produce_png(self) -> None:
        for view in ("top", "front", "side"):
            png = render_view(_records(), view=view, dpi=72, kernel=_KERNEL)
            assert png.startswith(_PNG_MAGIC)

    def test_views_differ(self) -> None:
        top = render_view(_records(), view="top", dpi=96, kernel=_KERNEL)
        side = render_view(_records(), view="side", dpi=96, kernel=_KERNEL)
        assert top != side

    def test_dpi_boundaries_accepted(self) -> None:
        render_view(_records(), view="top", dpi=72, kernel=_KERNEL)
        render_view(_records(), view="top", dpi=300, kernel=_KERNEL)

    def test_invalid_view_rejected(self) -> None:
        import pytest

        with pytest.raises(CADValidationError):
            render_view(_records(), view="isometric", kernel=_KERNEL)

    def test_dpi_out_of_range_rejected(self) -> None:
        import pytest

        with pytest.raises(CADValidationError):
            render_view(_records(), view="top", dpi=600, kernel=_KERNEL)
        with pytest.raises(CADValidationError):
            render_view(_records(), view="top", dpi=10, kernel=_KERNEL)

    def test_writes_output_file(self, tmp_path) -> None:
        target = tmp_path / "render.png"
        png = render_view(_records(), view="front", output=str(target), kernel=_KERNEL)
        assert target.exists()
        assert target.read_bytes() == png

    def test_empty_scene_renders(self) -> None:
        png = render_view([], view="top", kernel=_KERNEL)
        assert png.startswith(_PNG_MAGIC)


class TestRenderer3D:
    """3D preview PNG rendering."""

    def test_render_3d_png(self) -> None:
        png = render_3d(_records(), dpi=96, kernel=_KERNEL)
        assert png.startswith(_PNG_MAGIC)
        assert len(png) > 1000

    def test_render_3d_without_solids(self) -> None:
        records = [_Record(_KERNEL.create_line([0, 0, 0], [1, 1, 1]))]
        png = render_3d(records, dpi=72, kernel=_KERNEL)
        assert png.startswith(_PNG_MAGIC)

    def test_render_3d_dpi_out_of_range(self) -> None:
        import pytest

        with pytest.raises(CADValidationError):
            render_3d(_records(), dpi=400, kernel=_KERNEL)


class TestWebGLExport:
    """Three.js BufferGeometry export."""

    def test_export_webgl_structure(self) -> None:
        data = export_webgl(_records(), kernel=_KERNEL)
        assert data["metadata"]["format"] == "webgl-buffer-geometry"
        assert data["objectCount"] == 3
        assert len(data["positions"]) > 0
        assert len(data["indices"]) > 0
        assert len(data["linePositions"]) > 0
        assert data["bounds"]["min"] == [0.0, 0.0, 0.0]

    def test_export_webgl_indexed_triangles(self) -> None:
        data = export_webgl(_records(), kernel=_KERNEL)
        for triangle in data["indices"]:
            assert len(triangle) == 3
            for index in triangle:
                assert 0 <= index < len(data["positions"])

    def test_export_webgl_file(self, tmp_path) -> None:
        import json

        target = tmp_path / "scene.json"
        path = export_webgl_file(_records(), str(target), kernel=_KERNEL)
        assert path == str(target)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["objectCount"] == 3

    def test_export_empty_scene(self) -> None:
        data = export_webgl([], kernel=_KERNEL)
        assert data["objectCount"] == 0
        assert data["positions"] == []
        assert data["bounds"] == {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}

    def test_viewer_html_is_static_page(self) -> None:
        html = viewer_html()
        assert "<!DOCTYPE html>" in html
        assert "three.min.js" in html
        assert "OrbitControls" in html
