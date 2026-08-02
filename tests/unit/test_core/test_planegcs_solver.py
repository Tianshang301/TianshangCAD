"""planegcs constraint solver backend tests (Spike 1).

These tests exercise the optional ``[solver]`` backend adapter in
``cad_mcp_server.core.backends.planegcs_solver``. They are skipped
when planegcs is not installed (it requires Python >=3.12 and is an
optional extra), keeping the default ``pip install -e .`` test suite
green.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from cad_mcp_server.core.backends.planegcs_solver import (
    PlanegcsUnavailableError,
    apply_solution_planegcs,
    solve_2d_planegcs,
)
from cad_mcp_server.core.constraint import ConstraintManager, ConstraintType
from cad_mcp_server.core.entity import EntityManager

planegcs = pytest.importorskip("planegcs", reason="planegcs not installed (extra: solver)")

_SKIP_REASON = "planegcs requires Python >=3.12"


def _line(entity_manager: EntityManager, start: list[float], end: list[float]) -> str:
    return entity_manager.create("line", {"start": start, "end": end})


def _records(entity_manager: EntityManager, *entity_ids: str) -> dict:
    return {entity_id: entity_manager.get(entity_id) for entity_id in entity_ids}


def _solve(records: dict, manager: ConstraintManager) -> dict:
    return solve_2d_planegcs(records, manager.list())


def _direction(params: dict) -> np.ndarray:
    start = np.array(params["start"][:2])
    end = np.array(params["end"][:2])
    return end - start


class TestPlanegcsParallel:
    """planegcs backend makes two lines parallel."""

    def test_parallel_exact(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [0.0, 5.0, 0.0], [5.0, 8.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.PARALLEL, [anchor, movable])
        updates = _solve(_records(entity_manager, anchor, movable), manager)
        apply_solution_planegcs(entity_manager, updates)
        d1 = _direction(entity_manager.get(anchor).shape["params"])
        d2 = _direction(entity_manager.get(movable).shape["params"])
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        assert abs(cross) < 1e-6


class TestPlanegcsPerpendicular:
    """planegcs backend makes two lines perpendicular."""

    def test_perpendicular_exact(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [2.0, 3.0, 0.0], [2.0, 5.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.PERPENDICULAR, [anchor, movable])
        updates = _solve(_records(entity_manager, anchor, movable), manager)
        apply_solution_planegcs(entity_manager, updates)
        d1 = _direction(entity_manager.get(anchor).shape["params"])
        d2 = _direction(entity_manager.get(movable).shape["params"])
        assert abs(np.dot(d1, d2)) < 1e-6


class TestPlanegcsCoincident:
    """planegcs backend makes two points coincident."""

    def test_coincident_exact(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [10.0, 0.0, 0.0], [10.0, 10.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.COINCIDENT, [movable, anchor])
        updates = _solve(_records(entity_manager, anchor, movable), manager)
        apply_solution_planegcs(entity_manager, updates)
        start_a = entity_manager.get(anchor).shape["params"]["start"]
        start_b = entity_manager.get(movable).shape["params"]["start"]
        assert np.allclose(start_a[:2], start_b[:2], atol=1e-6)


class TestPlanegcsDistance:
    """planegcs backend constrains point-to-point distance."""

    def test_distance_exact(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [5.0, 3.0, 0.0], [5.0, 13.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.DISTANCE, [anchor, movable], {"distance": 5.0})
        updates = _solve(_records(entity_manager, anchor, movable), manager)
        apply_solution_planegcs(entity_manager, updates)
        a = np.array(entity_manager.get(anchor).shape["params"]["start"][:2])
        b = np.array(entity_manager.get(movable).shape["params"]["start"][:2])
        assert abs(np.linalg.norm(b - a) - 5.0) < 1e-6


class TestPlanegcsAngle:
    """planegcs backend constrains the angle between two lines."""

    def test_angle_90_exact(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [0.0, 5.0, 0.0], [8.0, 5.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.ANGLE, [anchor, movable], {"angle": 90.0})
        updates = _solve(_records(entity_manager, anchor, movable), manager)
        apply_solution_planegcs(entity_manager, updates)
        d1 = _direction(entity_manager.get(anchor).shape["params"])
        d2 = _direction(entity_manager.get(movable).shape["params"])
        cosine = np.dot(d1, d2) / (np.linalg.norm(d1) * np.linalg.norm(d2))
        assert abs(cosine) < 1e-6

    def test_angle_45_exact(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [0.0, 5.0, 0.0], [8.0, 5.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.ANGLE, [anchor, movable], {"angle": 45.0})
        updates = _solve(_records(entity_manager, anchor, movable), manager)
        apply_solution_planegcs(entity_manager, updates)
        d1 = _direction(entity_manager.get(anchor).shape["params"])
        d2 = _direction(entity_manager.get(movable).shape["params"])
        cosine = np.dot(d1, d2) / (np.linalg.norm(d1) * np.linalg.norm(d2))
        assert abs(cosine - math.cos(math.radians(45.0))) < 1e-6


class TestPlanegcsCombined:
    """Combined coincident+angle requires staged solving (Spike 1 finding)."""

    def test_coincident_angle_far_initial(self) -> None:
        # A coincident point far from its target combined with an angle
        # constraint is where the single-shot DogLeg solve is unreliable.
        # The adapter's staged strategy must converge exactly.
        for _ in range(5):
            entity_manager = EntityManager()
            anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
            movable = _line(entity_manager, [10.0, 0.0, 0.0], [10.0, 10.0, 0.0])
            manager = ConstraintManager()
            manager.add(ConstraintType.FIXED, [anchor])
            manager.add(ConstraintType.COINCIDENT, [movable, anchor])
            manager.add(ConstraintType.ANGLE, [anchor, movable], {"angle": 45.0})
            updates = _solve(_records(entity_manager, anchor, movable), manager)
            apply_solution_planegcs(entity_manager, updates)
            d1 = _direction(entity_manager.get(anchor).shape["params"])
            d2 = _direction(entity_manager.get(movable).shape["params"])
            cosine = np.dot(d1, d2) / (np.linalg.norm(d1) * np.linalg.norm(d2))
            assert abs(cosine - math.cos(math.radians(45.0))) < 1e-6


class TestPlanegcsUnavailable:
    """Backend surfaces a friendly error when planegcs is missing."""

    def test_raises_planegcs_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import cad_mcp_server.core.backends.planegcs_solver as module

        monkeypatch.setattr(module, "Sketch", None)
        monkeypatch.setattr(module, "SolveStatus", None)
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        with pytest.raises(PlanegcsUnavailableError):
            solve_2d_planegcs(_records(entity_manager, anchor), manager)
