"""Tests for the analytic CAD kernel."""

from __future__ import annotations

import pytest

from cad_mcp_server.core.kernel import AnalyticKernel, get_kernel
from cad_mcp_server.core.transform import rotation_z, translation
from cad_mcp_server.utils.errors import CADNotImplementedError, CADValidationError


class TestCreateAndBBox:
    """Shape creation and bounding box tests."""

    def test_line_bbox(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_line([0, 0, 0], [100, 0, 0])
        assert kernel.get_bbox(shape) == {
            "min": [0.0, 0.0, 0.0],
            "max": [100.0, 0.0, 0.0],
        }

    def test_circle_bbox(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_circle([50, 50, 0], 25)
        assert kernel.get_bbox(shape) == {
            "min": [25.0, 25.0, 0.0],
            "max": [75.0, 75.0, 0.0],
        }

    def test_box_bbox(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_box([0, 0, 0], [100, 50, 30])
        assert kernel.get_bbox(shape) == {
            "min": [0.0, 0.0, 0.0],
            "max": [100.0, 50.0, 30.0],
        }

    def test_sphere_bbox(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_sphere([10, 10, 10], 5)
        assert kernel.get_bbox(shape) == {
            "min": [5.0, 5.0, 5.0],
            "max": [15.0, 15.0, 15.0],
        }

    def test_cylinder_bbox(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_cylinder([0, 0, 0], radius=10, height=20)
        bbox = kernel.get_bbox(shape)
        assert bbox["min"] == [-10.0, -10.0, 0.0]
        assert bbox["max"] == [10.0, 10.0, 20.0]

    def test_rectangle_bbox_rotated(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_rectangle([0, 0, 0], width=10, height=10, rotation=45)
        bbox = kernel.get_bbox(shape)
        half_diagonal = 5 * 2**0.5
        assert bbox["min"][0] == pytest.approx(5 - half_diagonal, abs=1e-9)
        assert bbox["max"][0] == pytest.approx(5 + half_diagonal, abs=1e-9)

    def test_polygon_bbox(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_polygon([5, 5, 0], radius=10, sides=6)
        bbox = kernel.get_bbox(shape)
        assert bbox["min"][0] == pytest.approx(-5.0, abs=1e-9)
        assert bbox["max"][0] == pytest.approx(15.0, abs=1e-9)

    def test_polyline_bbox(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_polyline([[0, 0], [5, -5], [5, 8]], closed=True)
        assert kernel.get_bbox(shape) == {
            "min": [0.0, -5.0, 0.0],
            "max": [5.0, 8.0, 0.0],
        }

    def test_create_circle_invalid_radius(self, kernel: AnalyticKernel) -> None:
        with pytest.raises(CADValidationError):
            kernel.create_circle([0, 0, 0], -1)

    def test_create_polygon_too_few_sides(self, kernel: AnalyticKernel) -> None:
        with pytest.raises(CADValidationError):
            kernel.create_polygon([0, 0, 0], radius=5, sides=2)


class TestBoolean:
    """Analytic boolean operations on boxes."""

    def test_union_stacked(self, kernel: AnalyticKernel) -> None:
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([0, 0, 5], [10, 10, 10])
        result = kernel.boolean_union(a, b)
        assert kernel.get_bbox(result) == {
            "min": [0.0, 0.0, 0.0],
            "max": [10.0, 10.0, 15.0],
        }

    def test_union_contained(self, kernel: AnalyticKernel) -> None:
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([1, 1, 1], [2, 2, 2])
        assert kernel.boolean_union(a, b)["kind"] == "box"

    def test_union_disjoint_mesh(self, kernel: AnalyticKernel) -> None:
        trimesh = pytest.importorskip("trimesh")
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([50, 0, 0], [10, 10, 10])
        result = kernel.boolean_union(a, b)
        assert result["kind"] == "mesh"
        mesh = trimesh.Trimesh(
            vertices=result["params"]["vertices"],
            faces=result["params"]["faces"],
        )
        assert mesh.is_watertight
        assert kernel.get_bbox(result) == {
            "min": [0.0, 0.0, 0.0],
            "max": [60.0, 10.0, 10.0],
        }

    def test_union_corner_mesh(self, kernel: AnalyticKernel) -> None:
        trimesh = pytest.importorskip("trimesh")
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([5, 5, 5], [10, 10, 10])
        result = kernel.boolean_union(a, b)
        assert result["kind"] == "mesh"
        mesh = trimesh.Trimesh(
            vertices=result["params"]["vertices"],
            faces=result["params"]["faces"],
        )
        assert mesh.is_watertight
        assert kernel.get_bbox(result) == {
            "min": [0.0, 0.0, 0.0],
            "max": [15.0, 15.0, 15.0],
        }

    def test_union_missing_extra_raises(self, kernel: AnalyticKernel) -> None:
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([50, 0, 0], [10, 10, 10])
        import sys

        real_trimesh = sys.modules.pop("trimesh", None)
        try:
            sys.modules["trimesh"] = None  # type: ignore[assignment]
            with pytest.raises(CADNotImplementedError) as exc:
                kernel.boolean_union(a, b)
            assert exc.value.code == "requires_boolean"
        finally:
            if real_trimesh is not None:
                sys.modules["trimesh"] = real_trimesh
            else:
                sys.modules.pop("trimesh", None)

    def test_intersect(self, kernel: AnalyticKernel) -> None:
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([5, 5, 5], [10, 10, 10])
        result = kernel.boolean_intersect(a, b)
        assert kernel.get_bbox(result) == {
            "min": [5.0, 5.0, 5.0],
            "max": [10.0, 10.0, 10.0],
        }

    def test_subtract(self, kernel: AnalyticKernel) -> None:
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([5, -1, -1], [10, 12, 12])
        result = kernel.boolean_subtract(a, b)
        assert kernel.get_bbox(result) == {
            "min": [0.0, 0.0, 0.0],
            "max": [5.0, 10.0, 10.0],
        }

    def test_subtract_contains_target(self, kernel: AnalyticKernel) -> None:
        a = kernel.create_box([2, 2, 2], [3, 3, 3])
        b = kernel.create_box([0, 0, 0], [10, 10, 10])
        result = kernel.boolean_subtract(a, b)
        assert result["params"]["dimensions"] == [0.0, 0.0, 0.0]

    def test_subtract_splitting_mesh(self, kernel: AnalyticKernel) -> None:
        trimesh = pytest.importorskip("trimesh")
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([3, -1, -1], [4, 12, 12])
        result = kernel.boolean_subtract(a, b)
        assert result["kind"] == "mesh"
        mesh = trimesh.Trimesh(
            vertices=result["params"]["vertices"],
            faces=result["params"]["faces"],
        )
        assert mesh.is_watertight
        assert kernel.get_bbox(result) == {
            "min": [0.0, 0.0, 0.0],
            "max": [10.0, 10.0, 10.0],
        }

    def test_union_non_box_raises(self, kernel: AnalyticKernel) -> None:
        line = kernel.create_line([0, 0, 0], [1, 0, 0])
        box = kernel.create_box([0, 0, 0], [1, 1, 1])
        with pytest.raises(CADNotImplementedError):
            kernel.boolean_union(line, box)

    def test_disjoint_intersect_is_empty(self, kernel: AnalyticKernel) -> None:
        a = kernel.create_box([0, 0, 0], [1, 1, 1])
        b = kernel.create_box([5, 5, 5], [1, 1, 1])
        result = kernel.boolean_intersect(a, b)
        bbox = kernel.get_bbox(result)
        assert bbox["max"][0] == bbox["min"][0]


class TestTransform:
    """Kernel transform tests."""

    def test_translate_line(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_line([0, 0, 0], [10, 0, 0])
        moved = kernel.transform(shape, translation(5, 5, 0))
        assert kernel.get_bbox(moved) == {
            "min": [5.0, 5.0, 0.0],
            "max": [15.0, 5.0, 0.0],
        }

    def test_scale_circle(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_circle([0, 0, 0], 10)
        from cad_mcp_server.core.transform import scale

        scaled = kernel.transform(shape, scale(2, 2, 2))
        assert kernel.get_bbox(scaled) == {
            "min": [-20.0, -20.0, 0.0],
            "max": [20.0, 20.0, 0.0],
        }

    def test_rotate_line_about_origin(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_line([0, 0, 0], [10, 0, 0])
        rotated = kernel.transform(shape, rotation_z(90))
        bbox = kernel.get_bbox(rotated)
        assert bbox["min"][1] == pytest.approx(0.0, abs=1e-9)
        assert bbox["max"][1] == pytest.approx(10.0, abs=1e-9)


class TestTessellate:
    """Meshing tests."""

    def test_box_mesh(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_box([0, 0, 0], [10, 10, 10])
        vertices, faces = kernel.tessellate(shape)
        assert len(vertices) == 8
        assert len(faces) == 12

    def test_cylinder_mesh(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_cylinder([0, 0, 0], radius=5, height=10)
        vertices, faces = kernel.tessellate(shape)
        assert len(vertices) > 4
        assert len(faces) >= 8

    def test_sphere_mesh(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_sphere([0, 0, 0], 5)
        vertices, faces = kernel.tessellate(shape)
        assert len(vertices) > 10
        assert len(faces) > 20

    def test_cone_mesh(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_cone([0, 0, 0], radius_bottom=5, radius_top=0, height=10)
        vertices, faces = kernel.tessellate(shape)
        assert len(vertices) >= 2 + 24
        assert len(faces) >= 2 * 24

    def test_cone_mesh_watertight(self, kernel: AnalyticKernel) -> None:
        trimesh = pytest.importorskip("trimesh")
        shape = kernel.create_cone([0, 0, 0], radius_bottom=5, radius_top=2, height=10)
        vertices, faces = kernel.tessellate(shape)
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        assert mesh.is_watertight
        assert mesh.is_volume

    def test_line_tessellate_raises(self, kernel: AnalyticKernel) -> None:
        shape = kernel.create_line([0, 0, 0], [1, 0, 0])
        with pytest.raises(CADNotImplementedError):
            kernel.tessellate(shape)


class TestFactory:
    """Kernel factory tests."""

    def test_default_is_analytic(self) -> None:
        assert isinstance(get_kernel("analytic"), AnalyticKernel)

    def test_invalid_runtime(self) -> None:
        with pytest.raises(CADValidationError):
            get_kernel("quantum")

    def test_ocp_missing_backend(self) -> None:
        with pytest.raises(CADValidationError):
            get_kernel("ocp")

    def test_freecad_missing_backend(self) -> None:
        with pytest.raises(CADValidationError):
            get_kernel("freecad")
