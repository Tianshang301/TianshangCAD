"""Parametric feature core tests (analytic kernel)."""

from __future__ import annotations

import pytest

from tianshangcad.core.entity import EntityManager
from tianshangcad.core.features import FeatureManager
from tianshangcad.core.kernel import AnalyticKernel
from tianshangcad.utils.errors import CADNotImplementedError, CADValidationError


@pytest.fixture
def fm() -> FeatureManager:
    """Return a feature manager bound to the analytic kernel."""
    kernel = AnalyticKernel()
    return FeatureManager(EntityManager(kernel=kernel), kernel)


class TestSweep:
    """Analytic straight sweeps."""

    def test_sweep_circle_to_cylinder(self, fm: FeatureManager) -> None:
        cid = fm._entities.create("circle", {"center": [0, 0, 0], "radius": 5})
        sid = fm.sweep(cid, [[0, 0, 0], [0, 0, 20]])
        record = fm._entities.get(sid)
        assert record.type == "cylinder"
        bbox = fm._entities.get_bbox(sid)
        assert bbox["min"] == [-5.0, -5.0, 0.0]
        assert bbox["max"] == [5.0, 5.0, 20.0]

    def test_sweep_rectangle_to_box(self, fm: FeatureManager) -> None:
        rid = fm._entities.create("rectangle", {"origin": [0, 0, 0], "width": 4, "height": 3})
        sid = fm.sweep(rid, [[0, 0, 0], [10, 0, 0]])
        assert fm._entities.get(sid).type == "box"
        bbox = fm._entities.get_bbox(sid)
        assert bbox["min"] == [0.0, 0.0, -4.0]
        assert bbox["max"] == [10.0, 3.0, 0.0]

    def test_sweep_requires_at_least_two_points(self, fm: FeatureManager) -> None:
        cid = fm._entities.create("circle", {"center": [0, 0, 0], "radius": 1})
        with pytest.raises(CADValidationError):
            fm.sweep(cid, [[0, 0, 0]])

    def test_sweep_curved_path_requires_occ(self, fm: FeatureManager) -> None:
        cid = fm._entities.create("circle", {"center": [0, 0, 0], "radius": 1})
        with pytest.raises(CADNotImplementedError) as exc:
            fm.sweep(cid, [[0, 0, 0], [10, 0, 0], [10, 10, 0]])
        assert exc.value.code == "requires_occ"

    def test_sweep_unknown_profile_requires_occ(self, fm: FeatureManager) -> None:
        lid = fm._entities.create("line", {"start": [0, 0, 0], "end": [1, 0, 0]})
        with pytest.raises(CADNotImplementedError) as exc:
            fm.sweep(lid, [[0, 0, 0], [0, 0, 5]])
        assert exc.value.code == "requires_occ"


class TestLoft:
    """Analytic stacked-cone lofts."""

    def test_loft_concentric_circles_to_cone(self, fm: FeatureManager) -> None:
        c1 = fm._entities.create("circle", {"center": [0, 0, 0], "radius": 5})
        c2 = fm._entities.create("circle", {"center": [0, 0, 10], "radius": 8})
        lid = fm.loft([c1, c2])
        assert fm._entities.get(lid).type == "cone"
        bbox = fm._entities.get_bbox(lid)
        assert bbox["min"] == [-8.0, -8.0, 0.0]
        assert bbox["max"] == [8.0, 8.0, 10.0]

    def test_loft_equal_radii_is_cylinder(self, fm: FeatureManager) -> None:
        c1 = fm._entities.create("circle", {"center": [0, 0, 0], "radius": 5})
        c2 = fm._entities.create("circle", {"center": [0, 0, 10], "radius": 5})
        lid = fm.loft([c1, c2])
        params = fm._entities.get(lid).shape["params"]
        assert params["radius_bottom"] == params["radius_top"] == 5.0

    def test_loft_requires_two_profiles(self, fm: FeatureManager) -> None:
        c1 = fm._entities.create("circle", {"center": [0, 0, 0], "radius": 5})
        with pytest.raises(CADValidationError):
            fm.loft([c1])

    def test_loft_rectangle_requires_occ(self, fm: FeatureManager) -> None:
        r1 = fm._entities.create("rectangle", {"origin": [0, 0, 0], "width": 4, "height": 3})
        r2 = fm._entities.create("rectangle", {"origin": [0, 0, 10], "width": 6, "height": 5})
        with pytest.raises(CADNotImplementedError) as exc:
            fm.loft([r1, r2])
        assert exc.value.code == "requires_occ"


class TestFilletChamferAnalytic:
    """Fillet/chamfer report ``requires_occ`` on the analytic kernel."""

    def test_fillet_requires_occ(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
        with pytest.raises(CADNotImplementedError) as exc:
            fm.fillet(bid, 2.0)
        assert exc.value.code == "requires_occ"

    def test_chamfer_requires_occ(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
        with pytest.raises(CADNotImplementedError) as exc:
            fm.chamfer(bid, 2.0)
        assert exc.value.code == "requires_occ"

    def test_fillet_invalid_radius(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
        with pytest.raises(CADValidationError):
            fm.fillet(bid, -1.0)


class TestPatternLinear:
    """Linear patterns."""

    def test_counts_and_positions(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        ids = fm.pattern_linear(bid, [1, 0, 0], 3, 5.0)
        assert len(ids) == 3
        assert ids[0] == bid
        mins = [fm._entities.get_bbox(i)["min"] for i in ids]
        assert mins[0] == [0.0, 0.0, 0.0]
        assert mins[1] == [5.0, 0.0, 0.0]
        assert mins[2] == [10.0, 0.0, 0.0]

    def test_count_one_returns_original(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        ids = fm.pattern_linear(bid, [0, 1, 0], 1, 3.0)
        assert ids == [bid]

    def test_invalid_count(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        with pytest.raises(CADValidationError):
            fm.pattern_linear(bid, [1, 0, 0], 0, 3.0)


class TestPatternCircular:
    """Circular patterns."""

    def test_four_instances_around_origin(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        ids = fm.pattern_circular(bid, [0, 0, 0], [0, 0, 1], 4, 360.0)
        assert len(ids) == 4
        assert ids[0] == bid
        mins = [fm._entities.get_bbox(i)["min"] for i in ids]
        assert mins[1][0] == pytest.approx(-2.0, abs=1e-9)
        assert mins[1][1] == pytest.approx(0.0, abs=1e-9)
        assert mins[2][0] == pytest.approx(-2.0, abs=1e-9)
        assert mins[2][1] == pytest.approx(-2.0, abs=1e-9)

    def test_partial_span(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        ids = fm.pattern_circular(bid, [0, 0, 0], [0, 0, 1], 3, 180.0)
        assert len(ids) == 3

    def test_invalid_axis(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        with pytest.raises(CADValidationError):
            fm.pattern_circular(bid, [0, 0, 0], [0, 0, 0], 4, 360.0)


class TestPatternMirror:
    """Mirror patterns."""

    def test_mirror_across_xz_plane(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        mid = fm.pattern_mirror(bid, [0, 0, 0], [1, 0, 0])
        assert mid != bid
        bbox = fm._entities.get_bbox(mid)
        assert bbox["min"] == [-2.0, 0.0, 0.0]
        assert bbox["max"] == [0.0, 2.0, 2.0]

    def test_mirror_offset_plane(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        mid = fm.pattern_mirror(bid, [5, 0, 0], [1, 0, 0])
        bbox = fm._entities.get_bbox(mid)
        assert bbox["min"] == [8.0, 0.0, 0.0]
        assert bbox["max"] == [10.0, 2.0, 2.0]


class TestMetadataAttachment:
    """Pattern copies carry layer/properties/metadata."""

    def test_linear_layer_propagated(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        ids = fm.pattern_linear(bid, [1, 0, 0], 3, 5.0, layer="Bolt")
        assert fm._entities.get(bid).layer == "0"
        for i in ids[1:]:
            assert fm._entities.get(i).layer == "Bolt"

    def test_mirror_metadata_propagated(self, fm: FeatureManager) -> None:
        bid = fm._entities.create("box", {"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        mid = fm.pattern_mirror(bid, [0, 0, 0], [1, 0, 0], metadata={"role": "mirror"})
        assert fm._entities.get(mid).metadata.get("role") == "mirror"
