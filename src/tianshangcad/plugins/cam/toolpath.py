"""2.5-axis toolpath generation for the cam plugin.

Turns 2D profile entities (rectangle / polygon) into closed contour toolpaths
and circular entities (circle) into drill operations, at a fixed ``depth``.
The result is a :class:`Toolpath` of rapid/feed moves that the G-code emitter
serialises. Tool-radius compensation is out of scope: the outline is followed
directly.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from tianshangcad.core.kernel import CADKernel, get_kernel

#: Entity kinds treated as 2D contours.
_CONTOUR_KINDS = frozenset({"rectangle", "polygon"})
#: Entity kinds treated as drill sites (circle = hole centre).
_DRILL_KINDS = frozenset({"circle"})


@dataclass
class Move:
    """A single tool move (rapid or feed) in absolute coordinates."""

    x: float
    y: float
    z: float
    rapid: bool


@dataclass
class DrillOp:
    """A drill cycle at a single XY position."""

    x: float
    y: float
    depth: float


@dataclass
class Toolpath:
    """The generated 2.5-axis toolpath."""

    contours: list[list[Move]] = field(default_factory=list)
    drills: list[DrillOp] = field(default_factory=list)
    bounds: dict[str, list[float]] = field(
        default_factory=lambda: {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}
    )

    @property
    def move_count(self) -> int:
        """Total number of contour moves."""
        return sum(len(contour) for contour in self.contours) + 2 * len(self.drills)

    @property
    def path_length(self) -> float:
        """Total cutting path length in millimetres."""
        total = 0.0
        for contour in self.contours:
            for previous, current in pairwise(contour):
                total += math.hypot(current.x - previous.x, current.y - previous.y)
        return total


def _outline_points(shape: dict[str, Any], kernel: CADKernel) -> list[list[float]]:
    """Return the 2D outline of a contour entity (ignoring Z)."""
    kind = shape["kind"]
    if kind in _CONTOUR_KINDS:
        return kernel.outline_points(shape)
    return []


def build_toolpath(
    records: Sequence[Any],
    kernel: CADKernel | None = None,
    *,
    clearance: float = 5.0,
    depth: float = -10.0,
) -> Toolpath:
    """Generate a 2.5-axis toolpath from the given entities.

    ``clearance`` is the retract height above the XY plane and ``depth`` the
    cutting depth (negative = below the plane).
    """
    active = kernel or get_kernel()
    toolpath = Toolpath()
    all_points: list[list[float]] = []

    for record in records:
        shape = record.shape
        kind = shape["kind"]
        params = shape["params"]
        if kind in _DRILL_KINDS:
            center = params["center"]
            toolpath.drills.append(DrillOp(x=float(center[0]), y=float(center[1]), depth=depth))
            all_points.append([center[0], center[1], depth])
            continue
        if kind not in _CONTOUR_KINDS:
            continue
        outline = _outline_points(shape, active)
        if len(outline) < 2:
            continue
        # Start above the first point, plunge, cut the closed outline, retract.
        start = outline[0]
        moves = [Move(x=start[0], y=start[1], z=clearance, rapid=True)]
        for point in outline[1:]:
            moves.append(Move(x=point[0], y=point[1], z=depth, rapid=False))
        moves.append(Move(x=start[0], y=start[1], z=depth, rapid=False))
        moves.append(Move(x=start[0], y=start[1], z=clearance, rapid=True))
        toolpath.contours.append(moves)
        for point in outline:
            all_points.append([point[0], point[1], depth])

    if all_points:
        xs = [point[0] for point in all_points]
        ys = [point[1] for point in all_points]
        zs = [point[2] for point in all_points]
        toolpath.bounds = {
            "min": [min(xs), min(ys), min(zs)],
            "max": [max(xs), max(ys), max(zs)],
        }
    return toolpath
