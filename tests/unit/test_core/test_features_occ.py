"""OCCT-backed feature tests (Phase 8, optional ``[occ]`` extra).

These exercises run against ``tianshangcad.core.backends.occt`` and are
skipped when cadquery is not installed. They verify the exact sweep / loft
/ fillet / chamfer paths dispatched through :class:`FeatureManager`.
"""

from __future__ import annotations

import pytest

pytest.importorskip("cadquery", reason="cadquery not installed (extra: occ)")

from tianshangcad.core.backends.occt import OCCTKernel
from tianshangcad.core.entity import EntityManager
from tianshangcad.core.features import FeatureManager


def _kernel() -> OCCTKernel:
    return OCCTKernel()


def _fm() -> FeatureManager:
    kernel = _kernel()
    return FeatureManager(EntityManager(kernel=kernel), kernel)


class TestOCCTFeatures:
    """Exact OCCT feature geometry."""

    def test_sweep_circle_returns_mesh(self) -> None:
        fm = _fm()
        cid = fm._entities.create("circle", {"center": [0, 0, 0], "radius": 5})
        sid = fm.sweep(cid, [[0, 0, 0], [0, 0, 20]])
        record = fm._entities.get(sid)
        assert record.type == "mesh"
        assert len(record.shape["params"]["vertices"]) > 0
        bbox = fm._entities.get_bbox(sid)
        assert bbox["max"][2] - bbox["min"][2] == pytest.approx(30.0, rel=0.05)

    def test_loft_circles_returns_mesh(self) -> None:
        fm = _fm()
        c1 = fm._entities.create("circle", {"center": [0, 0, 0], "radius": 5})
        c2 = fm._entities.create("circle", {"center": [0, 0, 10], "radius": 8})
        lid = fm.loft([c1, c2], sections=[[0, 0, 0], [0, 0, 10]])
        record = fm._entities.get(lid)
        assert record.type == "mesh"
        assert len(record.shape["params"]["vertices"]) > 0

    def test_fillet_box(self) -> None:
        fm = _fm()
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [10, 20, 30]})
        fid = fm.fillet(bid, 2.0)
        record = fm._entities.get(fid)
        assert record.type == "mesh"
        assert len(record.shape["params"]["vertices"]) > 0
        assert fm._entities.get_bbox(fid)["max"] == pytest.approx([10.0, 20.0, 30.0])

    def test_chamfer_box(self) -> None:
        fm = _fm()
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [10, 20, 30]})
        cid = fm.chamfer(bid, 2.0)
        record = fm._entities.get(cid)
        assert record.type == "mesh"
        assert len(record.shape["params"]["vertices"]) > 0

    def test_fillet_too_large_reports_requires_occ(self) -> None:
        fm = _fm()
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [4, 4, 4]})
        from tianshangcad.utils.errors import CADNotImplementedError

        with pytest.raises(CADNotImplementedError):
            fm.fillet(bid, 10.0)

    def test_patterns_on_occt_kernel(self) -> None:
        fm = _fm()
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        ids = fm.pattern_linear(bid, [1, 0, 0], 3, 5.0)
        assert len(ids) == 3
        mins = [fm._entities.get_bbox(i)["min"] for i in ids]
        assert mins[2][0] == pytest.approx(10.0)
