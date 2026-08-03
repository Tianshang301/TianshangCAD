"""FreeCAD backend (system dependency, primarily for Linux/Docker)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from cad_mcp_server.core.kernel import CADKernel, Shape
from cad_mcp_server.utils.errors import CADNotImplementedError

Point = Sequence[float]


class FreeCADKernel(CADKernel):
    """CAD kernel backed by FreeCAD / OpenCASCADE.

    FreeCAD ships its own Python runtime, so integration from a regular
    virtual environment requires ``FREECAD_LIB`` to point at the FreeCAD
    installation. Full implementation is a later-phase work item.
    """

    def __init__(self) -> None:
        """Initialise the FreeCAD kernel wrapper."""
        raise CADNotImplementedError(
            "FreeCAD backend is not wired up yet; use runtime=analytic or ocp",
            code="backend_unavailable",
        )

    def create_line(self, start: Point, end: Point) -> Shape:
        """Create a line segment from ``start`` to ``end``."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_circle(self, center: Point, radius: float) -> Shape:
        """Create a circle with the given centre and radius."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_arc(
        self,
        center: Point,
        radius: float,
        start_angle: float,
        end_angle: float,
    ) -> Shape:
        """Create a circular arc (angles in degrees)."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_rectangle(
        self,
        origin: Point,
        width: float,
        height: float,
        rotation: float = 0.0,
    ) -> Shape:
        """Create a rectangle."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_polygon(
        self,
        center: Point,
        radius: float,
        sides: int,
        rotation: float = 0.0,
    ) -> Shape:
        """Create a regular polygon."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_polyline(self, points: Sequence[Point], closed: bool = False) -> Shape:
        """Create a polyline through ``points``."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_box(
        self,
        origin: Point,
        dimensions: Point,
        rotation: Sequence[float] | Sequence[Sequence[float]] | None = None,
    ) -> Shape:
        """Create an axis-aligned (or rotated) box."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_cylinder(
        self,
        origin: Point,
        radius: float,
        height: float,
        axis: Point = (0, 0, 1),
    ) -> Shape:
        """Create a cylinder."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_sphere(self, center: Point, radius: float) -> Shape:
        """Create a sphere."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def create_cone(
        self,
        origin: Point,
        radius_bottom: float,
        radius_top: float,
        height: float,
    ) -> Shape:
        """Create a cone or frustum."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def boolean_union(self, target: Shape, tool: Shape) -> Shape:
        """Boolean union of two shapes."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def boolean_subtract(self, target: Shape, tool: Shape) -> Shape:
        """Boolean subtraction: target minus tool."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def boolean_intersect(self, target: Shape, tool: Shape) -> Shape:
        """Boolean intersection of two shapes."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def get_bbox(self, shape: Shape) -> dict[str, list[float]]:
        """Return ``{min: [x, y, z], max: [x, y, z]}`` bounding box."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def transform(self, shape: Shape, matrix: Any) -> Shape:
        """Return a new shape with ``matrix`` (4x4) applied."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def tessellate(
        self,
        shape: Shape,
        deflection: float = 0.1,
    ) -> tuple[list[list[float]], list[list[int]]]:
        """Return ``(vertices, faces)`` triangular mesh of ``shape``."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")

    def copy_shape(self, shape: Shape) -> Shape:
        """Return a deep copy of ``shape``."""
        raise CADNotImplementedError("FreeCAD backend not wired up", code="unsupported_backend")
