"""Constraint manager and solver unit tests."""

from __future__ import annotations

import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from cad_mcp_server.core.constraint import ConstraintManager, ConstraintType
from cad_mcp_server.core.entity import EntityManager
from cad_mcp_server.core.solver import apply_solution, solve_2d
from cad_mcp_server.utils.errors import ConstraintError


def _line(entity_manager: EntityManager, start: list[float], end: list[float]) -> str:
    return entity_manager.create("line", {"start": start, "end": end})


def _circle(
    entity_manager: EntityManager, center: list[float], radius: float
) -> str:
    return entity_manager.create("circle", {"center": center, "radius": radius})


class TestConstraintManager:
    """Constraint manager CRUD and serialization."""

    def test_add_parallel(self) -> None:
        manager = ConstraintManager()
        record = manager.add(ConstraintType.PARALLEL, ["l1", "l2"])
        assert record.type == ConstraintType.PARALLEL
        assert record.entities == ["l1", "l2"]
        assert manager.count() == 1

    def test_add_accepts_string_type(self) -> None:
        manager = ConstraintManager()
        record = manager.add("tangent", ["c1", "l1"])
        assert record.type == ConstraintType.TANGENT

    def test_add_invalid_arity(self) -> None:
        manager = ConstraintManager()
        with pytest.raises(ConstraintError):
            manager.add(ConstraintType.PARALLEL, ["l1"])

    def test_add_duplicate_entity(self) -> None:
        manager = ConstraintManager()
        with pytest.raises(ConstraintError):
            manager.add(ConstraintType.PARALLEL, ["l1", "l1"])

    def test_remove(self) -> None:
        manager = ConstraintManager()
        record = manager.add(ConstraintType.FIXED, ["l1"])
        manager.remove(record.id)
        assert manager.count() == 0
        with pytest.raises(ConstraintError):
            manager.get(record.id)

    def test_remove_missing(self) -> None:
        with pytest.raises(ConstraintError):
            ConstraintManager().remove("nope")

    def test_list_filter_by_entity(self) -> None:
        manager = ConstraintManager()
        manager.add(ConstraintType.PARALLEL, ["a", "b"])
        manager.add(ConstraintType.TANGENT, ["c", "b"])
        assert len(manager.list(entity_id="b")) == 2
        assert len(manager.list(entity_id="a")) == 1

    def test_snapshot_restore(self) -> None:
        manager = ConstraintManager()
        manager.add(ConstraintType.PARALLEL, ["a", "b"], {"distance": 5.0})
        snapshot = manager.snapshot()
        manager.clear()
        manager.restore(snapshot)
        records = manager.list()
        assert len(records) == 1
        assert records[0].type == ConstraintType.PARALLEL
        assert records[0].params["distance"] == 5.0

    def test_to_dict_from_dict_roundtrip(self) -> None:
        manager = ConstraintManager()
        manager.add(ConstraintType.ANGLE, ["a", "b"], {"angle": 45.0})
        data = manager.list()[0].to_dict()
        from cad_mcp_server.core.constraint import ConstraintRecord

        restored = ConstraintRecord.from_dict(data)
        assert restored.type == ConstraintType.ANGLE
        assert restored.entities == ["a", "b"]
        assert restored.params["angle"] == 45.0


class TestParallelSolver:
    """Solver makes two lines parallel while keeping one anchored."""

    def _setup(self) -> tuple[EntityManager, str, str]:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [0.0, 5.0, 0.0], [5.0, 8.0, 0.0])
        return entity_manager, anchor, movable

    def test_parallel_converges(self) -> None:
        entity_manager, anchor, movable = self._setup()
        records = {"anchor": entity_manager.get(anchor), "movable": entity_manager.get(movable)}
        constraints = [
            ConstraintManager().add(ConstraintType.FIXED, ["anchor"]),
            ConstraintManager().add(ConstraintType.PARALLEL, ["anchor", "movable"]),
        ]
        result = solve_2d(records, constraints)
        assert result.converged
        assert result.updates["movable"]

    def test_parallel_applied(self) -> None:
        entity_manager, anchor, movable = self._setup()
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.PARALLEL, [anchor, movable])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, movable)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        anchor_params = entity_manager.get(anchor).shape["params"]
        movable_params = entity_manager.get(movable).shape["params"]
        d1 = _direction(anchor_params)
        d2 = _direction(movable_params)
        assert abs(_cross(d1, d2)) < 1e-6

    def test_parallel_requires_two(self) -> None:
        entity_manager = EntityManager()
        line_a = _line(entity_manager, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        records = {line_a: entity_manager.get(line_a)}
        manager = ConstraintManager()
        manager.add(ConstraintType.PARALLEL, [line_a, "missing"])
        with pytest.raises(ConstraintError):
            solve_2d(records, manager.list())


class TestPerpendicularSolver:
    """Solver makes two lines perpendicular."""

    def test_perpendicular_converges(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [2.0, 3.0, 0.0], [2.0, 5.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.PERPENDICULAR, [anchor, movable])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, movable)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        d1 = _direction(entity_manager.get(anchor).shape["params"])
        d2 = _direction(entity_manager.get(movable).shape["params"])
        assert abs(_dot(d1, d2)) < 1e-6


class TestCircleSolver:
    """Solver constrains a circle's centre onto a line midpoint."""

    def test_circle_center_on_line_midpoint(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        circle = _circle(entity_manager, [2.0, 3.0, 0.0], 1.0)
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.MIDPOINT, [circle, anchor])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, circle)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        center = entity_manager.get(circle).shape["params"]["center"]
        assert abs(center[0] - 5.0) < 1e-6
        assert abs(center[1] - 0.0) < 1e-6

    def test_circle_center_on_line(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        circle = _circle(entity_manager, [4.0, 2.0, 0.0], 1.0)
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.ON_LINE, [circle, anchor])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, circle)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        center = entity_manager.get(circle).shape["params"]["center"]
        assert abs(center[1]) < 1e-6

    def test_circle_tangent_to_line(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        circle = _circle(entity_manager, [5.0, 3.0, 0.0], 2.0)
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.TANGENT, [circle, anchor])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, circle)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        center = entity_manager.get(circle).shape["params"]["center"]
        radius = entity_manager.get(circle).shape["params"]["radius"]
        assert abs(abs(center[1]) - radius) < 1e-6


class TestCoincidentDistanceAngle:
    """Remaining constraint types."""

    def test_coincident_points(self) -> None:
        entity_manager = EntityManager()
        line_a = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        line_b = _line(entity_manager, [5.0, 5.0, 0.0], [15.0, 5.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.COINCIDENT, [line_a, line_b])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (line_a, line_b)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        start_b = entity_manager.get(line_b).shape["params"]["start"]
        start_a = entity_manager.get(line_a).shape["params"]["start"]
        assert abs(start_b[0] - start_a[0]) < 1e-6
        assert abs(start_b[1] - start_a[1]) < 1e-6

    def test_distance_between_points(self) -> None:
        entity_manager = EntityManager()
        circle_a = _circle(entity_manager, [0.0, 0.0, 0.0], 1.0)
        circle_b = _circle(entity_manager, [10.0, 0.0, 0.0], 1.0)
        manager = ConstraintManager()
        manager.add(ConstraintType.DISTANCE, [circle_a, circle_b], {"distance": 3.0})
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (circle_a, circle_b)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        a = entity_manager.get(circle_a).shape["params"]["center"]
        b = entity_manager.get(circle_b).shape["params"]["center"]
        assert abs(math.hypot(b[0] - a[0], b[1] - a[1]) - 3.0) < 1e-6

    def test_angle_between_lines(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [0.0, 5.0, 0.0], [8.0, 5.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.ANGLE, [anchor, movable], {"angle": 90.0})
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, movable)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        d1 = _direction(entity_manager.get(anchor).shape["params"])
        d2 = _direction(entity_manager.get(movable).shape["params"])
        cosine = _dot(d1, d2) / (math.hypot(*d1) * math.hypot(*d2))
        assert abs(cosine) < 1e-6


class TestSolverRobustness:
    """Degenerate and edge-case behaviour."""

    def test_no_constraints(self) -> None:
        entity_manager = EntityManager()
        line_a = _line(entity_manager, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        result = solve_2d({line_a: entity_manager.get(line_a)}, [])
        assert result.converged
        assert result.updates == {}

    def test_unsupported_entity_type(self) -> None:
        entity_manager = EntityManager()
        box = entity_manager.create("box", {"origin": [0, 0, 0], "dimensions": [1, 1, 1]})
        line_a = _line(entity_manager, [0.0, 0.0, 0.0], [1.0, 0.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.PARALLEL, [box, line_a])
        records = {eid: entity_manager.get(eid) for eid in (box, line_a)}
        with pytest.raises(ConstraintError):
            solve_2d(records, manager.list())

    def test_inconsistent_system_does_not_crash(self) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        movable = _line(entity_manager, [0.0, 5.0, 0.0], [8.0, 5.0, 0.0])
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.PARALLEL, [anchor, movable])
        manager.add(ConstraintType.PERPENDICULAR, [anchor, movable])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, movable)}
        result = solve_2d(records, manager.list())
        if result.converged:
            # The only simultaneous solution is a degenerate (zero-length) line.
            movable_params = result.updates[movable]
            start = movable_params["start"]
            end = movable_params["end"]
            assert abs(end[0] - start[0]) < 1e-6 and abs(end[1] - start[1]) < 1e-6


def _direction(params: dict) -> tuple[float, float]:
    start = params["start"]
    end = params["end"]
    return (end[0] - start[0], end[1] - start[1])


def _unit(v: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(v[0], v[1])
    if length < 1e-12:
        return (0.0, 0.0)
    return (v[0] / length, v[1] / length)


def _cross(u: tuple[float, float], v: tuple[float, float]) -> float:
    return u[0] * v[1] - u[1] * v[0]


def _dot(u: tuple[float, float], v: tuple[float, float]) -> float:
    return u[0] * v[0] + u[1] * v[1]


@st.composite
def _parallel_scenarios(draw: st.DrawFn) -> tuple[EntityManager, str, str]:
    entity_manager = EntityManager()
    anchor = _line(
        entity_manager,
        [0.0, 0.0, 0.0],
        [draw(st.floats(min_value=1.0, max_value=20.0)), 0.0, 0.0],
    )
    start_x = draw(st.floats(min_value=-10.0, max_value=10.0))
    start_y = draw(st.floats(min_value=-10.0, max_value=10.0))
    end_x = draw(st.floats(min_value=-10.0, max_value=10.0))
    end_y = draw(st.floats(min_value=-10.0, max_value=10.0))
    movable = _line(entity_manager, [start_x, start_y, 0.0], [end_x, end_y, 0.0])
    return entity_manager, anchor, movable


class TestSolverFuzz:
    """Hypothesis-driven fuzz tests for the constraint solver."""

    @given(_parallel_scenarios())
    @settings(max_examples=50)
    def test_parallel_holds_for_random_lines(self, scenario: tuple) -> None:
        entity_manager, anchor, movable = scenario
        if _direction(entity_manager.get(movable).shape["params"]) == (0.0, 0.0):
            return
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.PARALLEL, [anchor, movable])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, movable)}
        result = solve_2d(records, manager.list())
        apply_solution(entity_manager, result)
        assert result.converged
        d1 = _unit(_direction(entity_manager.get(anchor).shape["params"]))
        d2 = _unit(_direction(entity_manager.get(movable).shape["params"]))
        assert abs(_cross(d1, d2)) < 1e-6

    @given(
        st.floats(min_value=-20.0, max_value=20.0),
        st.floats(min_value=-20.0, max_value=20.0),
    )
    @settings(max_examples=50)
    def test_circle_center_on_midpoint_arbitrary_start(
        self, start_x: float, start_y: float
    ) -> None:
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [10.0, 0.0, 0.0])
        circle = _circle(entity_manager, [start_x, start_y, 0.0], 1.0)
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.MIDPOINT, [circle, anchor])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, circle)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        center = entity_manager.get(circle).shape["params"]["center"]
        assert abs(center[0] - 5.0) < 1e-6
        assert abs(center[1]) < 1e-6

    @given(
        st.floats(min_value=0.5, max_value=10.0),
        st.floats(min_value=-8.0, max_value=8.0),
        st.floats(min_value=0.5, max_value=5.0),
    )
    @settings(max_examples=50)
    def test_tangent_distance_consistent(
        self, line_length: float, center_y: float, radius: float
    ) -> None:
        if abs(center_y) < 1e-6:
            return
        entity_manager = EntityManager()
        anchor = _line(entity_manager, [0.0, 0.0, 0.0], [line_length, 0.0, 0.0])
        circle = _circle(entity_manager, [5.0, center_y, 0.0], radius)
        manager = ConstraintManager()
        manager.add(ConstraintType.FIXED, [anchor])
        manager.add(ConstraintType.TANGENT, [circle, anchor])
        records = {entity_id: entity_manager.get(entity_id) for entity_id in (anchor, circle)}
        result = solve_2d(records, manager.list())
        assert result.converged
        apply_solution(entity_manager, result)
        center = entity_manager.get(circle).shape["params"]["center"]
        new_radius = entity_manager.get(circle).shape["params"]["radius"]
        assert abs(abs(center[1]) - new_radius) < 1e-6
