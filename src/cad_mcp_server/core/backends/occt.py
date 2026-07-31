"""OCCT backend based on ``cadquery``/``ocp`` (optional extra)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from cad_mcp_server.core.kernel import CADKernel, Shape
from cad_mcp_server.utils.errors import CADNotImplementedError

Point = Sequence[float]


class OCCTKernel(CADKernel):
    """CAD kernel backed by the OCCT bindings (cadquery).

    Requires ``pip install -e '.[occ]'``. The full implementation is
    planned together with the STEP/IGES pipeline in later phases.
    """

    def __init__(self) -> None:
        """Initialise the OCCT kernel by importing ``cadquery``."""
        try:
            import cadquery  # type: ignore[import-not-found]
        except ImportError as exc:
            raise CADNotImplementedError(
                "OCCT backend requires cadquery; run `pip install -e '.[occ]'`",
                code="backend_unavailable",
            ) from exc
        self._cadquery = cadquery

    def create_line(self, start: Point, end: Point) -> Shape:
        """Create a line segment from ``start`` to ``end``."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_circle(self, center: Point, radius: float) -> Shape:
        """Create a circle with the given centre and radius."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_arc(
        self,
        center: Point,
        radius: float,
        start_angle: float,
        end_angle: float,
    ) -> Shape:
        """Create a circular arc (angles in degrees)."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_rectangle(
        self,
        origin: Point,
        width: float,
        height: float,
        rotation: float = 0.0,
    ) -> Shape:
        """Create a rectangle."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_polygon(
        self,
        center: Point,
        radius: float,
        sides: int,
        rotation: float = 0.0,
    ) -> Shape:
        """Create a regular polygon."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_polyline(self, points: Sequence[Point], closed: bool = False) -> Shape:
        """Create a polyline through ``points``."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_box(
        self,
        origin: Point,
        dimensions: Point,
        rotation: Sequence[float] | None = None,
    ) -> Shape:
        """Create an axis-aligned (or rotated) box."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_cylinder(
        self,
        origin: Point,
        radius: float,
        height: float,
        axis: Point = (0, 0, 1),
    ) -> Shape:
        """Create a cylinder."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_sphere(self, center: Point, radius: float) -> Shape:
        """Create a sphere."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def create_cone(
        self,
        origin: Point,
        radius_bottom: float,
        radius_top: float,
        height: float,
    ) -> Shape:
        """Create a cone or frustum."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def boolean_union(self, target: Shape, tool: Shape) -> Shape:
        """Boolean union of two shapes."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def boolean_subtract(self, target: Shape, tool: Shape) -> Shape:
        """Boolean subtraction: target minus tool."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def boolean_intersect(self, target: Shape, tool: Shape) -> Shape:
        """Boolean intersection of two shapes."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def get_bbox(self, shape: Shape) -> dict[str, list[float]]:
        """Return ``{min: [x, y, z], max: [x, y, z]}`` bounding box."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def transform(self, shape: Shape, matrix: Any) -> Shape:
        """Return a new shape with ``matrix`` (4x4) applied."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def tessellate(
        self,
        shape: Shape,
        deflection: float = 0.1,
    ) -> tuple[list[list[float]], list[list[int]]]:
        """Return ``(vertices, faces)`` triangular mesh of ``shape``."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )

    def copy_shape(self, shape: Shape) -> Shape:
        """Return a deep copy of ``shape``."""
        raise CADNotImplementedError(
            "OCCT backend is a Phase 4 work item",
            code="unsupported_backend",
        )
