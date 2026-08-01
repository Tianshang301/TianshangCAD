"""Tests for the 3D view render helpers."""

from __future__ import annotations

from cad_mcp_server.core.kernel import get_kernel
from cad_mcp_server.render.animation import render_orbit_gif
from cad_mcp_server.render.explode import explode_mesh
from cad_mcp_server.render.section import bounds_radius, section_mesh
from cad_mcp_server.render.webgl_exporter import export_webgl_delta
from cad_mcp_server.schemas.view3d import (
    CameraPose,
    ExplodeSpec,
    SectionPlane,
    camera_origin,
    fit_camera_to_bounds,
    named_view,
)


def _record(shape, entity_id: str = "a") -> object:
    record = type("Record", (), {})()
    record.shape = shape
    record.id = entity_id
    record.type = "box"
    record.layer = "0"
    return record


def _box_record(entity_id: str = "a"):
    kernel = get_kernel()
    return _record(kernel.create_box([0, 0, 0], [10, 5, 2]), entity_id)


class TestViewSchema:
    """view3d schema helpers."""

    def test_named_views(self) -> None:
        for name in ("iso", "top", "front", "side", "back", "bottom"):
            view = named_view(name)
            assert view.name == name
            assert view.camera.distance > 0

    def test_named_view_invalid(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            named_view("bogus")

    def test_camera_origin(self) -> None:
        camera = CameraPose(azimuth=0.0, elevation=0.0, distance=10.0, target=[0, 0, 0])
        origin = camera_origin(camera)
        assert origin[2] == 0.0
        assert abs(origin[0] - 10.0) < 1e-9

    def test_fit_camera_to_bounds(self) -> None:
        camera = fit_camera_to_bounds({"min": [0, 0, 0], "max": [100, 50, 30]})
        assert camera.target == [50.0, 25.0, 15.0]
        assert camera.distance > 0


class TestSection:
    """section_mesh helper."""

    def test_box_section_keeps_portion(self) -> None:
        kernel = get_kernel()
        record = _box_record()
        kept, cut = section_mesh(
            [record], SectionPlane(plane="XY", offset=1.0), kernel=kernel
        )
        assert len(kept) > 0
        assert len(cut) > 0
        for triangle in kept:
            for vertex in triangle:
                assert vertex[2] >= 1.0 - 1e-6

    def test_section_beyond_bounds_empty(self) -> None:
        kernel = get_kernel()
        record = _box_record()
        kept, _cut = section_mesh(
            [record], SectionPlane(plane="XY", offset=999.0), kernel=kernel
        )
        assert kept == []

    def test_bounds_radius(self) -> None:
        kernel = get_kernel()
        radius = bounds_radius([_box_record()], kernel=kernel)
        assert radius > 0


class TestExplode:
    """explode_mesh helper."""

    def test_explode_moves_vertices(self) -> None:
        kernel = get_kernel()
        record = _box_record()
        triangles = explode_mesh(
            [record], ExplodeSpec(offset_x=1.0), kernel=kernel
        )
        assert len(triangles) > 0
        xs = [vertex[0] for triangle in triangles for vertex in triangle]
        assert max(xs) > 10.0  # displaced along +X beyond the box extent

    def test_explode_zero_offsets_unchanged(self) -> None:
        kernel = get_kernel()
        record = _box_record()
        triangles = explode_mesh([record], ExplodeSpec(), kernel=kernel)
        xs = [vertex[0] for triangle in triangles for vertex in triangle]
        assert max(xs) <= 10.0 + 1e-6


class TestAnimation:
    """render_orbit_gif helper."""

    def test_gif_output(self) -> None:
        kernel = get_kernel()
        gif = render_orbit_gif(
            [_box_record()],
            frames=4,
            fps=5,
            kernel=kernel,
            camera=CameraPose(azimuth=45.0, elevation=35.264, distance=20.0),
        )
        assert gif[:6] in (b"GIF87a", b"GIF89a")

    def test_gif_writes_output(self, tmp_path) -> None:
        kernel = get_kernel()
        target = tmp_path / "orbit.gif"
        render_orbit_gif(
            [_box_record()],
            frames=4,
            fps=5,
            output=str(target),
            kernel=kernel,
        )
        assert target.exists()
        assert target.read_bytes()[:6] == b"GIF89a"


class TestWebGLDelta:
    """export_webgl_delta helper."""

    def test_delta_add_remove(self) -> None:
        kernel = get_kernel()
        a = _box_record("a")
        b = _record(kernel.create_sphere([20, 0, 0], 3), "b")
        b.type = "sphere"
        delta = export_webgl_delta(["a"], [a, b], kernel=kernel)
        assert delta["added"] == ["b"]
        assert delta["removed"] == []
        assert "a" in delta["updated"]
        assert "b" in delta["geometries"]

    def test_delta_remove_only(self) -> None:
        kernel = get_kernel()
        b = _record(kernel.create_sphere([0, 0, 0], 3), "b")
        delta = export_webgl_delta(["a", "b"], [b], kernel=kernel)
        assert delta["removed"] == ["a"]
        assert delta["added"] == []
