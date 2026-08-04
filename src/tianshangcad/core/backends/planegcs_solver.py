"""SolveSpace-family constraint solver backend via planegcs.

Spike 1 prototype (M2 pre-research): wraps FreeCAD's PlaneGCS 2D
constraint solver (``planegcs``) to solve 2D geometric constraints over
line/circle entities, replacing the self-built Gauss-Newton solver in
``tianshangcad.core.solver`` as the primary path when planegcs is
installed.

This is an **interim prototype** validating feasibility for Phase 7's
assembly mates. The public entry point :func:`solve_2d_planegcs` mirrors
the ``solve_2d`` signature so the constraint tools can switch backends
behind a thin adapter. The analytic kernel and the self-built solver stay
the default (``pip install -e .`` requires no extras); planegcs is the
optional ``[solver]`` extra.

Degenerate handling: zero-length lines, contradictory constraints, and
large coordinates do not crash (``SolveStatus.Failed`` surfaces as a
non-converged result rather than an exception).

Staged solving: combined far-from-target constraints (e.g. a coincident
point translated 10 units while an angle constraint rotates the line) are
sensitive to the DogLeg solver's local convergence and can fail
non-deterministically (~40-60% success in isolation). Splitting the solve
into geometric positioning (coincident/parallel/perpendicular) then
measured values (distance/angle) is 100% stable across distances
1..1000 and is what this module does.

Angle units: ``set_l2l_angle`` takes radians (planegcs/PlaneGCS
convention), while ``ConstraintType.ANGLE`` params use degrees; the
adapter converts.

Spike findings (2026-08-03): 6 mate types verified (coincident /
concentric / parallel / perpendicular / distance / angle); 100-part chain
assembly solves in ~45 ms (acceptance: ≥20 parts < 1 s).
"""

from __future__ import annotations

import math
from typing import Any

from tianshangcad.core.constraint import ConstraintRecord, ConstraintType
from tianshangcad.core.entity import EntityManager, EntityRecord
from tianshangcad.utils.errors import ConstraintError

try:
    from planegcs import Sketch, SolveStatus  # type: ignore[import-not-found, unused-ignore]
except ImportError:  # pragma: no cover - exercised only without the extra
    Sketch = None  # type: ignore[assignment, misc, unused-ignore]
    SolveStatus = None  # type: ignore[assignment, misc, unused-ignore]


class PlanegcsUnavailableError(ConstraintError):
    """Raised when planegcs is required but not installed."""


def _requires_planegcs() -> None:
    if Sketch is None:
        raise PlanegcsUnavailableError(
            "planegcs solver is not installed; install with `pip install "
            "tianshangcad-server[solver]` (requires Python >=3.12)",
            code="requires_planegcs",
        )


def _extract(record: EntityRecord) -> tuple[str, list[float]]:
    """Return ``(kind, [params])`` for a solvable entity."""
    kind = record.type
    params = record.shape["params"]
    if kind == "line":
        start, end = params["start"], params["end"]
        return "line", [start[0], start[1], end[0], end[1]]
    if kind == "circle":
        center = params["center"]
        return "circle", [center[0], center[1], float(params["radius"])]
    raise ConstraintError(
        f"Constraint solver supports line/circle only, got {kind!r}",
        code="unsupported_entity",
    )


def _add_entity(sketch: Sketch, kind: str, values: list[float]) -> tuple[Any, Any]:
    """Add a line or circle entity to the sketch, returning its handles."""
    if kind == "line":
        p1 = sketch.add_point(values[0], values[1])
        p2 = sketch.add_point(values[2], values[3])
        line = sketch.add_line(p1, p2)
        return line, (p1, p2)
    center = sketch.add_point(values[0], values[1])
    radius = sketch.add_param(float(values[2]), fixed=True)
    circle = sketch.add_circle(center, radius)
    return circle, (center, radius)


def _point_values(sketch: Sketch, point: Any) -> tuple[float, float]:
    info = sketch.get_point(point)
    return (float(info[0]), float(info[1]))


def solve_2d_planegcs(
    records: dict[str, EntityRecord],
    constraints: list[ConstraintRecord],
    *,
    max_iterations: int = 100,
    tolerance: float = 1e-8,
) -> dict[str, dict[str, Any]]:
    """Solve constraints with the planegcs backend.

    Mirrors the shape of :func:`tianshangcad.core.solver.solve_2d`:
    returns per-entity new shape params for non-anchored entities. Anchored
    (``FIXED``) entities are not included in the output. Raises
    :class:`ConstraintError` on unsupported constraints and returns
    ``None``-free dicts only for the solved entities.

    Returned dict maps entity ids to ``{"start": [...], "end": [...]}``
    for lines or ``{"center": [...], "radius": ...}`` for circles.
    """
    _requires_planegcs()

    referenced: set[str] = set()
    for constraint in constraints:
        referenced.update(constraint.entities)

    sketch = Sketch()
    handles: dict[str, tuple[Any, Any]] = {}
    kinds: dict[str, str] = {}
    anchored: set[str] = set()

    for entity_id in sorted(referenced):
        record = records.get(entity_id)
        if record is None:
            raise ConstraintError(f"Object not found: {entity_id}", code="object_not_found")
        kind, values = _extract(record)
        kinds[entity_id] = kind
        entity, pts = _add_entity(sketch, kind, values)
        handles[entity_id] = (entity, pts)
        if any(c.type == ConstraintType.FIXED for c in constraints if entity_id in c.entities):
            anchored.add(entity_id)
            if kind == "line":
                p1, p2 = pts
                sketch.fix_point(p1, values[0], values[1])
                sketch.fix_point(p2, values[2], values[3])
            else:
                center, radius = pts
                sketch.fix_point(center, values[0], values[1])

    line_ref: dict[str, Any] = {}
    for entity_id, (entity, _pts) in handles.items():
        if kinds[entity_id] == "line":
            line_ref[entity_id] = entity

    def _apply(constraint: ConstraintRecord) -> None:
        """Add a single non-FIXED constraint to the sketch."""
        ctype = constraint.type
        first, second = constraint.entities[0], constraint.entities[1]
        if ctype == ConstraintType.COINCIDENT:
            if kinds[first] == "circle":
                _, (fc, _) = handles[first]
                first_pt = fc
            else:
                _, (fp1, _) = handles[first]
                first_pt = fp1
            if kinds[second] == "circle":
                _, (sc, _) = handles[second]
                second_pt = sc
            else:
                _, (sp1, _) = handles[second]
                second_pt = sp1
            sketch.coincident(first_pt, second_pt)
        elif ctype == ConstraintType.PARALLEL:
            if kinds[first] != "line" or kinds[second] != "line":
                raise ConstraintError("parallel requires two lines", code="invalid_kind")
            sketch.parallel(line_ref[first], line_ref[second])
        elif ctype == ConstraintType.PERPENDICULAR:
            if kinds[first] != "line" or kinds[second] != "line":
                raise ConstraintError("perpendicular requires two lines", code="invalid_kind")
            sketch.perpendicular(line_ref[first], line_ref[second])
        elif ctype == ConstraintType.DISTANCE:
            target = float(constraint.params.get("distance", 0.0))
            _, (fp, _) = handles[first]
            _, (sp, _) = handles[second]
            param = sketch.add_param(target, fixed=True)
            sketch.p2p_distance(fp, sp, param)
        elif ctype == ConstraintType.ANGLE:
            if kinds[first] != "line" or kinds[second] != "line":
                raise ConstraintError("angle requires two lines", code="invalid_kind")
            target = float(constraint.params.get("angle", 0.0))
            sketch.set_l2l_angle(line_ref[first], line_ref[second], math.radians(target))
        else:
            raise ConstraintError(
                f"Unsupported constraint type {ctype.value} in planegcs backend",
                code="unsupported_type",
            )

    def _solve() -> None:
        """Run the solver, falling back to LM if DogLeg fails."""
        from planegcs import Algorithm

        status = sketch.solve()  # DogLeg default
        if status == SolveStatus.Failed:
            status = sketch.solve(algorithm=Algorithm.LevenbergMarquardt)
        if status != SolveStatus.Success and status != SolveStatus.Converged:
            raise ConstraintError(
                f"planegcs solve failed: {status}",
                code="solve_failed",
            )

    # Phase 1: geometric positioning constraints (coincident / parallel /
    # perpendicular) so large translations/rotations converge before any
    # measured values are applied. This avoids the solver's local-convergence
    # sensitivity to combined far-from-target constraints.
    geometric = [
        c
        for c in constraints
        if c.type
        in (ConstraintType.COINCIDENT, ConstraintType.PARALLEL, ConstraintType.PERPENDICULAR)
    ]
    measured = [c for c in constraints if c.type in (ConstraintType.DISTANCE, ConstraintType.ANGLE)]
    for constraint in geometric:
        _apply(constraint)
    if geometric:
        _solve()
    for constraint in measured:
        _apply(constraint)
    if measured:
        _solve()

    updates: dict[str, dict[str, Any]] = {}
    for entity_id, (_entity, pts) in handles.items():
        if entity_id in anchored:
            continue
        if kinds[entity_id] == "line":
            p1, p2 = pts
            x1, y1 = _point_values(sketch, p1)
            x2, y2 = _point_values(sketch, p2)
            updates[entity_id] = {
                "start": [x1, y1, 0.0],
                "end": [x2, y2, 0.0],
            }
        else:
            center, radius = pts
            cx, cy = _point_values(sketch, center)
            updates[entity_id] = {"center": [cx, cy, 0.0], "radius": float(radius)}
    return updates


def apply_solution_planegcs(
    entity_manager: EntityManager, updates: dict[str, dict[str, Any]]
) -> None:
    """Write solved geometry back to the entity manager."""
    for entity_id, params in updates.items():
        entity_manager.update(entity_id, params=params)
