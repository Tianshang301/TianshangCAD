"""2D geometric constraint solver (damped Gauss-Newton).

Solves a system of geometric constraints over line/circle entities in the
XY plane. Entities referenced by a ``fixed`` constraint are anchored
(constants); every other referenced entity contributes variables. The
numerical Jacobian is computed by central differences and the normal
equations are damped (Levenberg-Marquardt style), so under-constrained
systems converge to a minimal-movement least-squares solution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from cad_mcp_server.core.constraint import ConstraintRecord, ConstraintType
from cad_mcp_server.core.entity import EntityManager, EntityRecord
from cad_mcp_server.utils.errors import ConstraintError

DEFAULT_MAX_ITERATIONS = 100
DEFAULT_TOLERANCE = 1e-8
DEFAULT_DAMPING = 1e-3
_JACOBIAN_STEP = 1e-6
_MIN_RADIUS = 1e-12
_LENGTH_PRESERVE_WEIGHT = 1.0


@dataclass
class SolveResult:
    """Outcome of a constraint solve."""

    converged: bool
    iterations: int
    residual_norm: float
    updates: dict[str, dict[str, Any]]
    message: str


def _extract_params(record: EntityRecord) -> tuple[str, list[float]]:
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


def _rebuild_params(kind: str, record: EntityRecord, values: list[float]) -> dict[str, Any]:
    """Rebuild the shape params dict for an entity from solved values."""
    params = record.shape["params"]
    if kind == "line":
        start = list(params["start"])
        end = list(params["end"])
        start[0], start[1] = values[0], values[1]
        end[0], end[1] = values[2], values[3]
        return {"start": start, "end": end}
    center = list(params["center"])
    center[0], center[1] = values[0], values[1]
    return {"center": center, "radius": max(values[2], _MIN_RADIUS)}


def solve_2d(
    records: dict[str, EntityRecord],
    constraints: list[ConstraintRecord],
    *,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    tolerance: float = DEFAULT_TOLERANCE,
    damping: float = DEFAULT_DAMPING,
) -> SolveResult:
    """Solve constraints over the given entities.

    ``records`` maps entity ids to their current records. Constrained
    entities that are not anchored become variables; solved values are
    returned as new shape params in ``SolveResult.updates``. The geometry is
    **not** written back by this function.
    """
    referenced: set[str] = set()
    for constraint in constraints:
        referenced.update(constraint.entities)

    var_offsets: dict[str, int] = {}
    var_kinds: dict[str, str] = {}
    anchored: dict[str, tuple[str, list[float]]] = {}
    initial: list[float] = []
    line_lengths: dict[str, float] = {}
    circle_radii: dict[str, float] = {}

    for entity_id in sorted(referenced):
        record = records.get(entity_id)
        if record is None:
            raise ConstraintError(f"Object not found: {entity_id}", code="object_not_found")
        kind, values = _extract_params(record)
        if any(c.type == ConstraintType.FIXED for c in constraints if entity_id in c.entities):
            anchored[entity_id] = (kind, values)
        else:
            var_offsets[entity_id] = len(initial)
            var_kinds[entity_id] = kind
            initial.extend(values)
            if kind == "line":
                line_lengths[entity_id] = math.hypot(
                    values[2] - values[0], values[3] - values[1]
                )
            else:
                circle_radii[entity_id] = values[2]

    n = len(initial)
    if n == 0:
        return SolveResult(
            converged=True, iterations=0, residual_norm=0.0, updates={},
            message="Nothing to solve",
        )

    def _point(entity_id: str, index: int, x: np.ndarray) -> tuple[float, float]:
        if entity_id in var_offsets:
            offset = var_offsets[entity_id]
            kind = var_kinds[entity_id]
            if kind == "line":
                if index == 0:
                    return (float(x[offset]), float(x[offset + 1]))
                return (float(x[offset + 2]), float(x[offset + 3]))
            return (float(x[offset]), float(x[offset + 1]))
        kind, values = anchored[entity_id]
        if kind == "line":
            if index == 0:
                return (values[0], values[1])
            return (values[2], values[3])
        return (values[0], values[1])

    def _direction(entity_id: str, x: np.ndarray) -> tuple[float, float]:
        start = _point(entity_id, 0, x)
        end = _point(entity_id, 1, x)
        return (end[0] - start[0], end[1] - start[1])

    def _kind_of(entity_id: str) -> str:
        if entity_id in var_kinds:
            return var_kinds[entity_id]
        return anchored[entity_id][0]

    def _radius(entity_id: str, x: np.ndarray) -> float:
        if entity_id in var_offsets:
            offset = var_offsets[entity_id]
            return float(x[offset + 2])
        return float(anchored[entity_id][1][2])

    def _cross(u: tuple[float, float], v: tuple[float, float]) -> float:
        return u[0] * v[1] - u[1] * v[0]

    def _dot(u: tuple[float, float], v: tuple[float, float]) -> float:
        return u[0] * v[0] + u[1] * v[1]

    def _unit_direction(entity_id: str, x: np.ndarray) -> tuple[float, float]:
        dx, dy = _direction(entity_id, x)
        length = math.hypot(dx, dy)
        if length < _MIN_RADIUS:
            return (0.0, 0.0)
        return (dx / length, dy / length)

    def residual(x: np.ndarray) -> np.ndarray:
        rows: list[float] = []
        for constraint in constraints:
            ctype = constraint.type
            if ctype == ConstraintType.FIXED:
                continue
            first, second = constraint.entities[0], constraint.entities[1]
            if ctype == ConstraintType.COINCIDENT:
                pa = _point(first, int(constraint.params.get("point_a", 0)), x)
                pb = _point(second, int(constraint.params.get("point_b", 0)), x)
                rows.extend([pa[0] - pb[0], pa[1] - pb[1]])
            elif ctype == ConstraintType.PARALLEL:
                d1 = _unit_direction(first, x)
                d2 = _unit_direction(second, x)
                rows.append(_cross(d1, d2))
            elif ctype == ConstraintType.PERPENDICULAR:
                d1 = _unit_direction(first, x)
                d2 = _unit_direction(second, x)
                rows.append(_dot(d1, d2))
            elif ctype == ConstraintType.TANGENT:
                if {_kind_of(first), _kind_of(second)} != {"line", "circle"}:
                    raise ConstraintError(
                        "tangent requires a line and a circle", code="invalid_kind"
                    )
                circle_id = first if _kind_of(first) == "circle" else second
                line_id = second if circle_id == first else first
                center = _point(circle_id, 0, x)
                line_start = _point(line_id, 0, x)
                direction = _direction(line_id, x)
                length2 = _dot(direction, direction)
                radius = _radius(circle_id, x)
                cross = _cross(
                    (center[0] - line_start[0], center[1] - line_start[1]),
                    direction,
                )
                rows.append(cross * cross - radius * radius * length2)
            elif ctype == ConstraintType.ON_LINE:
                point = _point(first, int(constraint.params.get("point_a", 0)), x)
                line_start = _point(second, 0, x)
                direction = _direction(second, x)
                rows.append(
                    _cross((point[0] - line_start[0], point[1] - line_start[1]), direction)
                )
            elif ctype == ConstraintType.MIDPOINT:
                point = _point(first, int(constraint.params.get("point_a", 0)), x)
                start = _point(second, 0, x)
                end = _point(second, 1, x)
                rows.extend(
                    [
                        point[0] - (start[0] + end[0]) / 2.0,
                        point[1] - (start[1] + end[1]) / 2.0,
                    ]
                )
            elif ctype == ConstraintType.DISTANCE:
                pa = _point(first, int(constraint.params.get("point_a", 0)), x)
                pb = _point(second, int(constraint.params.get("point_b", 0)), x)
                target = float(constraint.params.get("distance", 0.0))
                dx = pa[0] - pb[0]
                dy = pa[1] - pb[1]
                rows.append((dx * dx + dy * dy) - target * target)
            elif ctype == ConstraintType.ANGLE:
                d1 = _unit_direction(first, x)
                d2 = _unit_direction(second, x)
                target = math.radians(float(constraint.params.get("angle", 0.0)))
                cosine = math.cos(target)
                sine = math.sin(target)
                rotated_x = d2[0] * cosine + d2[1] * sine
                rotated_y = -d2[0] * sine + d2[1] * cosine
                rows.append(_cross(d1, (rotated_x, rotated_y)))
            else:
                raise ConstraintError(
                    f"Unsupported constraint type {ctype.value}", code="unsupported_type"
                )
        for entity_id, target_length in line_lengths.items():
            if target_length > _MIN_RADIUS:
                direction = _direction(entity_id, x)
                current = math.hypot(direction[0], direction[1])
                rows.append(
                    _LENGTH_PRESERVE_WEIGHT * (current - target_length) / target_length
                )
        for entity_id, target_radius in circle_radii.items():
            if target_radius > _MIN_RADIUS:
                current = _radius(entity_id, x)
                rows.append(
                    _LENGTH_PRESERVE_WEIGHT * (current - target_radius) / target_radius
                )
        return np.asarray(rows, dtype=float)

    x = np.asarray(initial, dtype=float)
    lam = damping
    converged = False
    iterations = 0
    residual_norm = float("inf")

    def _jacobian(x_current: np.ndarray) -> np.ndarray:
        base = residual(x_current)
        rows = len(base)
        jac = np.zeros((rows, n))
        for i in range(n):
            step = _JACOBIAN_STEP * max(1.0, abs(x_current[i]))
            x_plus = x_current.copy()
            x_minus = x_current.copy()
            x_plus[i] += step
            x_minus[i] -= step
            jac[:, i] = (residual(x_plus) - residual(x_minus)) / (2.0 * step)
        return jac

    for _ in range(1, max_iterations + 1):
        iterations += 1
        residual_current = residual(x)
        residual_norm = float(np.linalg.norm(residual_current))
        if residual_norm < tolerance:
            converged = True
            break
        jac = _jacobian(x)
        try:
            normal = jac.T @ jac + lam * np.eye(n)
            gradient = jac.T @ residual_current
            delta = np.linalg.solve(normal, -gradient)
        except np.linalg.LinAlgError:
            lam *= 10.0
            continue
        if float(np.linalg.norm(delta)) < 1e-12 and lam < 1e6:
            rng = np.random.default_rng(0)
            jitter = rng.uniform(-1e-3, 1e-3, size=n) * (
                1.0 + np.abs(x)
            )
            x = x + jitter
            lam = DEFAULT_DAMPING
            continue
        candidate = x + delta
        if float(np.linalg.norm(residual(candidate))) < residual_norm:
            x = candidate
            lam = max(lam * 0.5, 1e-10)
        else:
            lam *= 10.0
            if lam > 1e12:
                break

    if not converged:
        residual_norm = float(np.linalg.norm(residual(x)))

    updates: dict[str, dict[str, Any]] = {}
    for entity_id, offset in var_offsets.items():
        kind = var_kinds[entity_id]
        size = 4 if kind == "line" else 3
        updates[entity_id] = _rebuild_params(
            kind, records[entity_id], list(x[offset : offset + size])
        )

    message = (
        "Constraints solved" if converged else f"Did not converge (residual {residual_norm:.3e})"
    )
    return SolveResult(
        converged=converged,
        iterations=iterations,
        residual_norm=residual_norm,
        updates=updates,
        message=message,
    )


def apply_solution(entity_manager: EntityManager, result: SolveResult) -> None:
    """Write solved geometry back to the entity manager."""
    for entity_id, params in result.updates.items():
        entity_manager.update(entity_id, params=params)
