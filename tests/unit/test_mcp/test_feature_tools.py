"""MCP parametric feature tool tests."""

from __future__ import annotations

import pytest

from cad_mcp_server.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from cad_mcp_server.mcp.tools.features import (
    FeatureChamferInput,
    FeatureFilletInput,
    FeatureLoftInput,
    FeaturePatternCircularInput,
    FeaturePatternLinearInput,
    FeaturePatternMirrorInput,
    FeatureSweepInput,
    cad_feature_chamfer,
    cad_feature_fillet,
    cad_feature_loft,
    cad_feature_pattern_circular,
    cad_feature_pattern_linear,
    cad_feature_pattern_mirror,
    cad_feature_sweep,
)


def _doc() -> None:
    cad_file_create(FileCreateInput(filename="features.json"))


class TestFeatureSweep:
    """`cad_feature_sweep` tests."""

    def test_sweep_circle(self) -> None:
        _doc()
        profile = cad_object_create(
            ObjectCreateInput(type="circle", params={"center": [0, 0, 0], "radius": 5})
        ).object_id
        result = cad_feature_sweep(
            FeatureSweepInput(profile_id=profile, path=[[0, 0, 0], [0, 0, 20]])
        )
        assert result.status == "success"
        assert result.object_id != ""
        assert result.bbox["max"] == [5.0, 5.0, 20.0]

    def test_sweep_unknown_profile(self) -> None:
        _doc()
        result = cad_feature_sweep(
            FeatureSweepInput(profile_id="nope", path=[[0, 0, 0], [0, 0, 5]])
        )
        assert result.status == "error"
        assert result.object_id == ""

    def test_sweep_no_document(self) -> None:
        result = cad_feature_sweep(
            FeatureSweepInput(profile_id="p", path=[[0, 0, 0], [0, 0, 5]])
        )
        assert result.status == "error"


class TestFeatureLoft:
    """`cad_feature_loft` tests."""

    def test_loft_circles(self) -> None:
        _doc()
        c1 = cad_object_create(
            ObjectCreateInput(type="circle", params={"center": [0, 0, 0], "radius": 5})
        ).object_id
        c2 = cad_object_create(
            ObjectCreateInput(type="circle", params={"center": [0, 0, 10], "radius": 8})
        ).object_id
        result = cad_feature_loft(FeatureLoftInput(profile_ids=[c1, c2]))
        assert result.status == "success"
        assert result.bbox["max"] == [8.0, 8.0, 10.0]


class TestFeatureFilletChamfer:
    """Fillet/chamfer report friendly errors on the analytic kernel."""

    def test_fillet_requires_occ(self) -> None:
        _doc()
        box = cad_object_create(
            ObjectCreateInput(type="box", params={"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
        ).object_id
        result = cad_feature_fillet(FeatureFilletInput(entity_id=box, radius=2.0))
        assert result.status == "error"
        assert "OCCT" in result.message

    def test_chamfer_requires_occ(self) -> None:
        _doc()
        box = cad_object_create(
            ObjectCreateInput(type="box", params={"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
        ).object_id
        result = cad_feature_chamfer(FeatureChamferInput(entity_id=box, size=2.0))
        assert result.status == "error"
        assert "OCCT" in result.message

    def test_fillet_invalid_radius(self) -> None:
        _doc()
        box = cad_object_create(
            ObjectCreateInput(type="box", params={"origin": [0, 0, 0], "dimensions": [10, 10, 10]})
        ).object_id
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FeatureFilletInput(entity_id=box, radius=-1.0)


class TestFeaturePatterns:
    """Pattern tools."""

    def _box(self) -> str:
        return cad_object_create(
            ObjectCreateInput(type="box", params={"origin": [0, 0, 0], "dimensions": [2, 2, 2]})
        ).object_id

    def test_pattern_linear(self) -> None:
        _doc()
        box = self._box()
        result = cad_feature_pattern_linear(
            FeaturePatternLinearInput(entity_id=box, direction=[1, 0, 0], count=3, spacing=5.0)
        )
        assert result.status == "success"
        assert result.count == 3
        assert result.object_ids[0] == box
        assert len(result.object_ids) == 3

    def test_pattern_circular(self) -> None:
        _doc()
        box = self._box()
        result = cad_feature_pattern_circular(
            FeaturePatternCircularInput(
                entity_id=box, center=[0, 0, 0], axis=[0, 0, 1], count=4, angle=360.0
            )
        )
        assert result.status == "success"
        assert result.count == 4

    def test_pattern_mirror(self) -> None:
        _doc()
        box = self._box()
        result = cad_feature_pattern_mirror(
            FeaturePatternMirrorInput(
                entity_id=box, plane_point=[0, 0, 0], plane_normal=[1, 0, 0]
            )
        )
        assert result.status == "success"
        assert result.object_id != ""

    def test_pattern_linear_invalid(self) -> None:
        _doc()
        box = self._box()
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FeaturePatternLinearInput(
                entity_id=box, direction=[1, 0, 0], count=0, spacing=5.0
            )
