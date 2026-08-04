"""Tests for the core geometry validation algorithms."""

from __future__ import annotations

import numpy as np

from tianshangcad.core.kernel import AnalyticKernel
from tianshangcad.core.validation import (
    _check_degenerate_faces,
    _check_non_manifold_edges,
    _check_self_intersection,
    bbox_volume,
    interference_volume,
    overlap_bbox,
    topology_stats,
    validate_entity,
)

_KERNEL = AnalyticKernel()


def _polyline_shape(points: list[list[float]], closed: bool = False) -> dict:
    return {
        "kind": "polyline",
        "params": {"points": points, "closed": closed},
    }


def _mesh_shape(vertices: list[list[float]], faces: list[list[int]]) -> dict:
    return {"kind": "mesh", "params": {"vertices": vertices, "faces": faces}}


class TestSelfIntersection:
    """Edge / edge self-intersection detection."""

    def test_simple_polyline_is_clean(self) -> None:
        shape = _polyline_shape([[0, 0], [1, 0], [1, 1], [0, 1]])
        issues = _check_self_intersection(shape, _KERNEL)
        assert issues == []

    def test_bowtie_detected(self) -> None:
        shape = _polyline_shape([[0, 0], [1, 1], [0, 1], [1, 0]])
        issues = _check_self_intersection(shape, _KERNEL)
        assert len(issues) == 1
        issue = issues[0]
        assert issue.issue_type == "self_intersection"
        assert issue.location is not None
        assert issue.fix_suggestion
        assert issue.details["segment_a"] != issue.details["segment_b"]

    def test_closed_polyline_last_segment_checked(self) -> None:
        shape = _polyline_shape([[0, 0], [2, 0], [2, 2], [0, 2]], closed=True)
        issues = _check_self_intersection(shape, _KERNEL)
        assert issues == []

    def test_rectangle_outline_clean(self) -> None:
        shape = _KERNEL.create_rectangle([0, 0, 0], 5, 3)
        assert _check_self_intersection(shape, _KERNEL) == []

    def test_adjacent_segments_not_flagged(self) -> None:
        shape = _polyline_shape([[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]])
        assert _check_self_intersection(shape, _KERNEL) == []


class TestDegenerateFaces:
    """Zero-area face detection."""

    def test_clean_mesh(self) -> None:
        shape = _mesh_shape(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[0, 1, 2], [0, 2, 3]],
        )
        assert _check_degenerate_faces(shape) == []

    def test_collinear_face_detected(self) -> None:
        shape = _mesh_shape(
            [[0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0]],
            [[0, 1, 2]],
        )
        issues = _check_degenerate_faces(shape)
        assert len(issues) == 1
        assert issues[0].issue_type == "degenerate_face"
        assert "zero area" in issues[0].message
        assert issues[0].fix_suggestion

    def test_short_face_detected(self) -> None:
        shape = _mesh_shape(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            [[0, 1]],
        )
        issues = _check_degenerate_faces(shape)
        assert len(issues) == 1
        assert issues[0].details["vertex_count"] == 2


class TestNonManifoldEdges:
    """Non-manifold edge detection."""

    def test_clean_mesh_manifold(self) -> None:
        shape = _mesh_shape(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[0, 1, 2], [0, 2, 3], [0, 3, 1]],
        )
        assert _check_non_manifold_edges(shape) == []

    def test_edge_shared_by_three_faces(self) -> None:
        shape = _mesh_shape(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [0, -1, 0]],
            [[0, 1, 2], [0, 1, 3], [1, 0, 4]],
        )
        issues = _check_non_manifold_edges(shape)
        assert len(issues) == 1
        assert issues[0].issue_type == "non_manifold_edge"
        assert issues[0].details["faces"] == [0, 1, 2]
        assert "2" in issues[0].message


class TestTopologyStats:
    """Topological statistics."""

    def test_box_stats(self) -> None:
        shape = _KERNEL.create_box([0, 0, 0], [1, 2, 3])
        stats = topology_stats(shape)
        assert stats["kind"] == "box"
        assert stats["vertices"] == 8
        assert stats["faces"] == 6
        assert stats["edges"] == 12

    def test_mesh_stats(self) -> None:
        shape = _mesh_shape(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[0, 1, 2], [0, 2, 3], [0, 3, 1]],
        )
        stats = topology_stats(shape)
        assert stats["vertices"] == 4
        assert stats["faces"] == 3
        assert stats["non_manifold_edges"] == 0
        assert stats["is_manifold"] is True

    def test_mesh_stats_non_manifold(self) -> None:
        shape = _mesh_shape(
            [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]],
            [[0, 1, 2], [0, 1, 3], [0, 1, 0]],
        )
        stats = topology_stats(shape)
        assert stats["non_manifold_edges"] == 1
        assert stats["is_manifold"] is False


class TestInterferenceVolume:
    """Bounding box overlap and volume helpers."""

    def test_overlap_volume(self) -> None:
        a = {"min": [0, 0, 0], "max": [10, 10, 10]}
        b = {"min": [5, 5, 5], "max": [15, 15, 15]}
        assert interference_volume(a, b) == 125.0

    def test_disjoint_volume_zero(self) -> None:
        a = {"min": [0, 0, 0], "max": [10, 10, 10]}
        b = {"min": [20, 20, 20], "max": [30, 30, 30]}
        assert interference_volume(a, b) == 0.0

    def test_touching_boxes_no_overlap(self) -> None:
        a = {"min": [0, 0, 0], "max": [10, 10, 10]}
        b = {"min": [10, 0, 0], "max": [20, 10, 10]}
        assert interference_volume(a, b) == 0.0

    def test_overlap_bbox(self) -> None:
        a = {"min": [0, 0, 0], "max": [10, 10, 10]}
        b = {"min": [5, 5, 5], "max": [15, 15, 15]}
        overlap = overlap_bbox(a, b)
        assert overlap == {"min": [5, 5, 5], "max": [10, 10, 10]}

    def test_bbox_volume(self) -> None:
        assert bbox_volume({"min": [0, 0, 0], "max": [2, 3, 4]}) == 24.0

    def test_bbox_volume_invalid(self) -> None:
        assert bbox_volume({"min": [0, 0, 0], "max": [0, 3, 4]}) == 0.0


class TestValidateEntity:
    """End-to-end per-entity validation."""

    def test_clean_entity_no_issues(self) -> None:
        shape = _polyline_shape([[0, 0], [1, 0], [1, 1], [0, 1]])
        issues = validate_entity("obj_a", shape, _KERNEL)
        assert issues == []

    def test_bowtie_entity_issue(self) -> None:
        shape = _polyline_shape([[0, 0], [1, 1], [0, 1], [1, 0]])
        issues = validate_entity("obj_a", shape, _KERNEL)
        assert len(issues) == 1
        assert issues[0].object_id == "obj_a"
        assert issues[0].issue_type == "self_intersection"

    def test_to_dict_shape(self) -> None:
        shape = _polyline_shape([[0, 0], [1, 1], [0, 1], [1, 0]])
        data = validate_entity("obj_a", shape, _KERNEL)[0].to_dict()
        assert data["type"] == "self_intersection"
        assert data["fix_suggestion"]
        assert data["location"] is not None

    def test_sphere_has_no_structural_issues(self) -> None:
        shape = _KERNEL.create_sphere([0, 0, 0], 5)
        assert validate_entity("obj_s", shape, _KERNEL) == []


class TestNumpyAuxiliary:
    """Direct checks on low-level math helpers."""

    def test_segment_intersection_point(self) -> None:
        from tianshangcad.core.validation import _segment_intersection

        a = np.array([0.0, 0.0])
        b = np.array([2.0, 2.0])
        c = np.array([0.0, 2.0])
        d = np.array([2.0, 0.0])
        point = _segment_intersection(a, b, c, d)
        assert point is not None
        assert abs(point[0] - 1.0) < 1e-6
        assert abs(point[1] - 1.0) < 1e-6
