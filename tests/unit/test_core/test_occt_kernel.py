"""OCCT kernel tests (Spike 2 pre-research).

These tests exercise the optional ``[occ]`` backend in
``cad_mcp_server.core.backends.occt`` (cadquery / OCP). They are skipped
when cadquery is not installed, keeping the default ``pip install -e .``
test suite green. The occ extra requires numpy <2 (cadquery 2.4 uses
nptyping which references removed numpy aliases).
"""

from __future__ import annotations

import os
import tempfile

import pytest

pytest.importorskip("cadquery", reason="cadquery not installed (extra: occ)")

from cad_mcp_server.core.backends.occt import OCCTKernel
from cad_mcp_server.utils.errors import CADValidationError


def _kernel() -> OCCTKernel:
    return OCCTKernel()


class TestOCCTCreate:
    """OCCT primitive creation and bounding boxes."""

    def test_box_bbox(self) -> None:
        kernel = _kernel()
        shape = kernel.create_box([0, 0, 0], [10, 20, 30])
        assert kernel.get_bbox(shape) == {
            "min": [0.0, 0.0, 0.0],
            "max": [10.0, 20.0, 30.0],
        }

    def test_cylinder_bbox_base_at_origin(self) -> None:
        kernel = _kernel()
        shape = kernel.create_cylinder([0, 0, 0], 3, 20)
        bbox = kernel.get_bbox(shape)
        assert bbox["min"][2] == pytest.approx(0.0)
        assert bbox["max"][2] == pytest.approx(20.0)

    def test_sphere_bbox(self) -> None:
        kernel = _kernel()
        shape = kernel.create_sphere([5, 5, 5], 2)
        bbox = kernel.get_bbox(shape)
        assert bbox["min"] == pytest.approx([3.0, 3.0, 3.0])
        assert bbox["max"] == pytest.approx([7.0, 7.0, 7.0])

    def test_cone_bbox(self) -> None:
        kernel = _kernel()
        shape = kernel.create_cone([0, 0, 0], 5, 2, 10)
        bbox = kernel.get_bbox(shape)
        assert bbox["min"][2] == pytest.approx(0.0, abs=1e-4)
        assert bbox["max"][2] == pytest.approx(10.0, abs=1e-4)

    def test_rectangle_bbox(self) -> None:
        kernel = _kernel()
        shape = kernel.create_rectangle([0, 0, 0], 10, 5)
        bbox = kernel.get_bbox(shape)
        assert bbox["min"][:2] == pytest.approx([0.0, 0.0])
        assert bbox["max"][:2] == pytest.approx([10.0, 5.0])


class TestOCCTBoolean:
    """Exact OCC BRep booleans."""

    def test_subtract(self) -> None:
        kernel = _kernel()
        box = kernel.create_box([0, 0, 0], [20, 20, 10])
        hole = kernel.create_cylinder([10, 10, 0], 3, 20)
        result = kernel.boolean_subtract(box, hole)
        assert result["kind"] == "mesh"
        bbox = kernel.get_bbox(result)
        assert bbox["min"][2] == pytest.approx(0.0)
        assert bbox["max"][2] == pytest.approx(10.0)

    def test_union(self) -> None:
        kernel = _kernel()
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([10, 0, 0], [10, 10, 10])
        result = kernel.boolean_union(a, b)
        bbox = kernel.get_bbox(result)
        assert bbox["max"] == pytest.approx([20.0, 10.0, 10.0])

    def test_intersect(self) -> None:
        kernel = _kernel()
        a = kernel.create_box([0, 0, 0], [10, 10, 10])
        b = kernel.create_box([5, 0, 0], [10, 10, 10])
        result = kernel.boolean_intersect(a, b)
        bbox = kernel.get_bbox(result)
        assert bbox["min"][0] == pytest.approx(5.0)
        assert bbox["max"][0] == pytest.approx(10.0)


class TestOCCTFeatures:
    """Phase 8 feature primitives (sweep / loft) validated by Spike 2."""

    def test_sweep(self) -> None:
        kernel = _kernel()
        profile = kernel.create_circle([0, 0, 0], 2.0)
        path = [[0, 0, 0], [30, 0, 0]]
        result = kernel.sweep(profile, path)
        assert result["kind"] == "mesh"
        bbox = kernel.get_bbox(result)
        assert bbox["min"][0] == pytest.approx(0.0)
        assert bbox["max"][0] == pytest.approx(30.0)

    def test_loft(self) -> None:
        kernel = _kernel()
        rect1 = kernel.create_rectangle([0, 0, 0], 10, 10)
        rect2 = kernel.create_rectangle([0, 0, 0], 4, 4)
        result = kernel.loft([rect1, rect2], [[0, 0, 0], [0, 0, 30]])
        assert result["kind"] == "mesh"
        bbox = kernel.get_bbox(result)
        assert bbox["max"][2] == pytest.approx(30.0)


class TestOCCTExport:
    """STEP / IGES roundtrip consistency (Spike 2 pass criteria)."""

    def test_step_roundtrip_consistent(self) -> None:
        kernel = _kernel()
        box = kernel.create_box([0, 0, 0], [10, 20, 30])
        path = os.path.join(tempfile.gettempdir(), "spike2_occ_rt.step")
        kernel.export_step(box, path)
        reimported = kernel.import_step(path)
        assert reimported["kind"] == "mesh"
        bbox = kernel.get_bbox(reimported)
        assert bbox["max"] == pytest.approx([10.0, 20.0, 30.0], abs=1e-6)

    def test_iges_export_writes_file(self) -> None:
        kernel = _kernel()
        box = kernel.create_box([0, 0, 0], [10, 20, 30])
        path = os.path.join(tempfile.gettempdir(), "spike2_occ.igs")
        kernel.export_iges(box, path)
        assert os.path.getsize(path) > 0


class TestOCCTTransformTessellate:
    """Transform and tessellation."""

    def test_transform_translation(self) -> None:
        from cad_mcp_server.core.transform import translation

        kernel = _kernel()
        box = kernel.create_box([0, 0, 0], [10, 20, 30])
        moved = kernel.transform(box, translation(5, 5, 5))
        bbox = kernel.get_bbox(moved)
        assert bbox["min"] == pytest.approx([5.0, 5.0, 5.0])
        assert bbox["max"] == pytest.approx([15.0, 25.0, 35.0])

    def test_tessellate(self) -> None:
        kernel = _kernel()
        box = kernel.create_box([0, 0, 0], [2, 2, 2])
        vertices, faces = kernel.tessellate(box)
        assert len(vertices) >= 8
        assert len(faces) >= 12


class TestOCCTValidation:
    """Validation and unsupported-shape errors."""

    def test_invalid_box_size(self) -> None:
        kernel = _kernel()
        with pytest.raises(CADValidationError):
            kernel.create_box([0, 0, 0], [0, 10, 10])

    def test_outline_points(self) -> None:
        kernel = _kernel()
        rect = kernel.create_rectangle([0, 0, 0], 10, 5)
        points = kernel.outline_points(rect)
        assert len(points) == 4
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        assert max(xs) - min(xs) == pytest.approx(10.0)
        assert max(ys) - min(ys) == pytest.approx(5.0)
