"""CAD kernel abstraction.

``CADKernel`` is the abstract geometry interface. ``AnalyticKernel`` is a
pure-Python / numpy implementation used by default so that the whole
system works without heavyweight native dependencies. Optional backends
(OCCT via ``cadquery`` and FreeCAD) may be selected through the
``CAD_RUNTIME`` setting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

import numpy as np

from cad_mcp_server.utils.config import get_settings
from cad_mcp_server.utils.errors import CADNotImplementedError, CADValidationError

Point = Sequence[float]
Shape = dict[str, Any]

_BOX_ROTATION_SIZE = 9

#: Shape kinds that represent closed 3D solids eligible for mesh boolean ops.
_SOLID_KINDS = frozenset({"box", "cylinder", "sphere", "cone", "mesh"})


def _ensure_dims(values: Sequence[float], dims: int = 3) -> list[float]:
    """Pad/truncate ``values`` to exactly ``dims`` floats."""
    result = [float(value) for value in values]
    while len(result) < dims:
        result.append(0.0)
    return result[:dims]


class CADKernel(ABC):
    """Abstract CAD geometry kernel interface.

    All geometry-producing methods return backend-specific ``Shape``
    objects. The analytic backend returns plain JSON-serialisable dicts.
    """

    @abstractmethod
    def create_line(self, start: Point, end: Point) -> Shape:
        """Create a line segment from ``start`` to ``end``."""

    @abstractmethod
    def create_circle(self, center: Point, radius: float) -> Shape:
        """Create a circle with the given centre and radius."""

    @abstractmethod
    def create_arc(
        self,
        center: Point,
        radius: float,
        start_angle: float,
        end_angle: float,
    ) -> Shape:
        """Create a circular arc (angles in degrees)."""

    @abstractmethod
    def create_rectangle(
        self,
        origin: Point,
        width: float,
        height: float,
        rotation: float = 0.0,
    ) -> Shape:
        """Create a rectangle."""

    @abstractmethod
    def create_polygon(
        self, center: Point, radius: float, sides: int, rotation: float = 0.0
    ) -> Shape:
        """Create a regular polygon."""

    @abstractmethod
    def create_polyline(self, points: Sequence[Point], closed: bool = False) -> Shape:
        """Create a polyline through ``points``."""

    @abstractmethod
    def create_box(
        self, origin: Point, dimensions: Point, rotation: Sequence[float] | None = None
    ) -> Shape:
        """Create an axis-aligned (or rotated) box."""

    @abstractmethod
    def create_cylinder(
        self, origin: Point, radius: float, height: float, axis: Point = (0, 0, 1)
    ) -> Shape:
        """Create a cylinder."""

    @abstractmethod
    def create_sphere(self, center: Point, radius: float) -> Shape:
        """Create a sphere."""

    @abstractmethod
    def create_cone(
        self,
        origin: Point,
        radius_bottom: float,
        radius_top: float,
        height: float,
    ) -> Shape:
        """Create a cone or frustum."""

    @abstractmethod
    def boolean_union(self, target: Shape, tool: Shape) -> Shape:
        """Boolean union of two shapes."""

    @abstractmethod
    def boolean_subtract(self, target: Shape, tool: Shape) -> Shape:
        """Boolean subtraction: target minus tool."""

    @abstractmethod
    def boolean_intersect(self, target: Shape, tool: Shape) -> Shape:
        """Boolean intersection of two shapes."""

    @abstractmethod
    def get_bbox(self, shape: Shape) -> dict[str, list[float]]:
        """Return ``{min: [x, y, z], max: [x, y, z]}`` bounding box."""

    @abstractmethod
    def transform(self, shape: Shape, matrix: Any) -> Shape:
        """Return a new shape with ``matrix`` (4x4) applied."""

    @abstractmethod
    def tessellate(
        self, shape: Shape, deflection: float = 0.1
    ) -> tuple[list[list[float]], list[list[int]]]:
        """Return ``(vertices, faces)`` triangular mesh of ``shape``."""

    @abstractmethod
    def copy_shape(self, shape: Shape) -> Shape:
        """Return a deep copy of ``shape``."""


class AnalyticKernel(CADKernel):
    """Pure-Python analytic geometry kernel.

    Shapes are dicts of the form ``{"kind": <type>, "params": {...}}`` and
    are JSON-serialisable. Boolean operations are supported for
    axis-aligned boxes; other combinations raise ``CADNotImplementedError``.
    """

    def create_line(self, start: Point, end: Point) -> Shape:
        """Create a line segment from ``start`` to ``end``."""
        return {
            "kind": "line",
            "params": {
                "start": _ensure_dims(start),
                "end": _ensure_dims(end),
            },
        }

    def create_circle(self, center: Point, radius: float) -> Shape:
        """Create a circle with the given centre and radius."""
        if radius <= 0:
            raise CADValidationError("radius must be > 0", code="invalid_radius")
        return {
            "kind": "circle",
            "params": {"center": _ensure_dims(center), "radius": float(radius)},
        }

    def create_arc(
        self,
        center: Point,
        radius: float,
        start_angle: float,
        end_angle: float,
    ) -> Shape:
        """Create a circular arc (angles in degrees)."""
        if radius <= 0:
            raise CADValidationError("radius must be > 0", code="invalid_radius")
        return {
            "kind": "arc",
            "params": {
                "center": _ensure_dims(center),
                "radius": float(radius),
                "start_angle": float(start_angle) % 360.0,
                "end_angle": float(end_angle) % 360.0,
            },
        }

    def create_rectangle(
        self,
        origin: Point,
        width: float,
        height: float,
        rotation: float = 0.0,
    ) -> Shape:
        """Create a rectangle."""
        if width <= 0 or height <= 0:
            raise CADValidationError("width and height must be > 0", code="invalid_size")
        return {
            "kind": "rectangle",
            "params": {
                "origin": _ensure_dims(origin),
                "width": float(width),
                "height": float(height),
                "rotation": float(rotation),
            },
        }

    def create_polygon(
        self, center: Point, radius: float, sides: int, rotation: float = 0.0
    ) -> Shape:
        """Create a regular polygon."""
        if radius <= 0:
            raise CADValidationError("radius must be > 0", code="invalid_radius")
        if sides < 3:
            raise CADValidationError("sides must be >= 3", code="invalid_sides")
        return {
            "kind": "polygon",
            "params": {
                "center": _ensure_dims(center),
                "radius": float(radius),
                "sides": int(sides),
                "rotation": float(rotation),
            },
        }

    def create_polyline(self, points: Sequence[Point], closed: bool = False) -> Shape:
        """Create a polyline through ``points``."""
        if len(points) < 2:
            raise CADValidationError("polyline requires at least 2 points", code="invalid_points")
        return {
            "kind": "polyline",
            "params": {
                "points": [_ensure_dims(point) for point in points],
                "closed": bool(closed),
            },
        }

    def create_box(
        self,
        origin: Point,
        dimensions: Point,
        rotation: Sequence[float] | None = None,
    ) -> Shape:
        """Create an axis-aligned (or rotated) box."""
        dims = _ensure_dims(dimensions)
        if any(value <= 0 for value in dims):
            raise CADValidationError("box dimensions must all be > 0", code="invalid_size")
        rotation_matrix: list[list[float]] | None = None
        if rotation is not None:
            rotation_list = list(rotation)
            if len(rotation_list) == 3 and all(
                isinstance(row, (list, tuple)) and len(row) == 3 for row in rotation_list
            ):
                rotation_matrix = [
                    [float(value) for value in row]  # type: ignore[attr-defined]
                    for row in rotation_list
                ]
            else:
                rotation_matrix = self._rotation_to_matrix(rotation_list)
        return {
            "kind": "box",
            "params": {
                "origin": _ensure_dims(origin),
                "dimensions": dims,
                "rotation": rotation_matrix,
            },
        }

    def create_cylinder(
        self, origin: Point, radius: float, height: float, axis: Point = (0, 0, 1)
    ) -> Shape:
        """Create a cylinder."""
        if radius <= 0 or height <= 0:
            raise CADValidationError("radius and height must be > 0", code="invalid_size")
        return {
            "kind": "cylinder",
            "params": {
                "origin": _ensure_dims(origin),
                "radius": float(radius),
                "height": float(height),
                "axis": _ensure_dims(axis),
            },
        }

    def create_sphere(self, center: Point, radius: float) -> Shape:
        """Create a sphere."""
        if radius <= 0:
            raise CADValidationError("radius must be > 0", code="invalid_radius")
        return {
            "kind": "sphere",
            "params": {"center": _ensure_dims(center), "radius": float(radius)},
        }

    def create_cone(
        self,
        origin: Point,
        radius_bottom: float,
        radius_top: float,
        height: float,
    ) -> Shape:
        """Create a cone or frustum."""
        if radius_bottom < 0 or radius_top < 0 or height <= 0:
            raise CADValidationError("invalid cone parameters", code="invalid_size")
        return {
            "kind": "cone",
            "params": {
                "origin": _ensure_dims(origin),
                "radius_bottom": float(radius_bottom),
                "radius_top": float(radius_top),
                "height": float(height),
            },
        }

    # ------------------------------------------------------------------
    # Boolean operations
    # ------------------------------------------------------------------

    def boolean_union(self, target: Shape, tool: Shape) -> Shape:
        """Boolean union of two shapes.

        Box pairs use an exact fast path when the result is a single box;
        otherwise solid shapes are tessellated and combined with the mesh
        boolean engine (``pip install -e '.[boolean]'``).
        """
        if target["kind"] == "box" and tool["kind"] == "box":
            try:
                return self._box_union(target, tool)
            except CADNotImplementedError:
                pass
        return self._mesh_boolean("union", target, tool)

    def boolean_subtract(self, target: Shape, tool: Shape) -> Shape:
        """Boolean subtraction: target minus tool."""
        if target["kind"] == "box" and tool["kind"] == "box":
            try:
                return self._box_subtract(target, tool)
            except CADNotImplementedError:
                pass
        return self._mesh_boolean("difference", target, tool)

    def boolean_intersect(self, target: Shape, tool: Shape) -> Shape:
        """Boolean intersection of two shapes."""
        if target["kind"] == "box" and tool["kind"] == "box":
            try:
                return self._box_intersect(target, tool)
            except CADNotImplementedError:
                pass
        return self._mesh_boolean("intersection", target, tool)

    def _box_union(self, target: Shape, tool: Shape) -> Shape:
        """Exact union for box pairs whose result is a single box."""
        self._require_box_pair(target, tool, "union")
        a_min, a_max = _bbox_arrays(target)
        b_min, b_max = _bbox_arrays(tool)
        if not self._boxes_overlap(a_min, a_max, b_min, b_max):
            raise CADNotImplementedError(
                "union of disjoint boxes is not a single box",
                code="unsupported_boolean",
            )
        if self._box_contains(a_min, a_max, b_min, b_max):
            return target
        if self._box_contains(b_min, b_max, a_min, a_max):
            return tool
        aligned = sum(
            1
            for i in range(3)
            if np.isclose(a_min[i], b_min[i]) and np.isclose(a_max[i], b_max[i])
        )
        if aligned < 2:
            raise CADNotImplementedError(
                "union of these boxes is not a single box",
                code="unsupported_boolean",
            )
        return self._box_from_bbox(
            np.minimum(a_min, b_min).tolist(),
            np.maximum(a_max, b_max).tolist(),
        )

    def _box_subtract(self, target: Shape, tool: Shape) -> Shape:
        """Exact subtraction for box pairs that yield a single box."""
        self._require_box_pair(target, tool, "subtract")
        a_min, a_max = _bbox_arrays(target)
        b_min, b_max = _bbox_arrays(tool)
        new_min = np.array(a_min, dtype=float)
        new_max = np.array(a_max, dtype=float)
        cutting_axes = 0
        for i in range(3):
            covers_full = b_min[i] <= a_min[i] and b_max[i] >= a_max[i]
            if covers_full:
                continue
            cutting_axes += 1
            if b_min[i] > a_min[i] and b_max[i] < a_max[i]:
                raise CADNotImplementedError(
                    "subtract that splits a box is not supported by AnalyticKernel",
                    code="unsupported_boolean",
                )
            if b_min[i] > a_min[i]:
                new_max[i] = b_min[i]
            else:
                new_min[i] = b_max[i]
        if cutting_axes == 0:
            return self._empty_box()
        if cutting_axes >= 2:
            raise CADNotImplementedError(
                "subtract would produce a non-box result",
                code="unsupported_boolean",
            )
        if any(new_max[i] <= new_min[i] for i in range(3)):
            return self._empty_box()
        return self._box_from_bbox(new_min.tolist(), new_max.tolist())

    def _box_intersect(self, target: Shape, tool: Shape) -> Shape:
        """Exact intersection for box pairs."""
        self._require_box_pair(target, tool, "intersect")
        a_min, a_max = _bbox_arrays(target)
        b_min, b_max = _bbox_arrays(tool)
        new_min = np.maximum(a_min, b_min)
        new_max = np.minimum(a_max, b_max)
        if any(new_max[i] <= new_min[i] for i in range(3)):
            return self._empty_box()
        return self._box_from_bbox(new_min.tolist(), new_max.tolist())

    def _mesh_boolean(self, operation: str, target: Shape, tool: Shape) -> Shape:
        """Boolean via the trimesh/manifold engine; returns a ``mesh`` shape.

        ``operation`` is one of ``union``, ``difference``, ``intersection``.
        Requires the optional ``boolean`` extra
        (``pip install -e '.[boolean]'``).
        """
        for shape in (target, tool):
            if shape["kind"] not in _SOLID_KINDS:
                raise CADNotImplementedError(
                    f"boolean {operation} requires solid shapes "
                    f"(box/cylinder/sphere/cone/mesh), not {shape['kind']}",
                    code="unsupported_boolean",
                )
        try:
            import trimesh
            from trimesh import boolean as trimesh_boolean
        except ImportError as exc:
            raise CADNotImplementedError(
                "Mesh boolean requires trimesh + manifold3d; "
                "run `pip install -e '.[boolean]'`",
                code="requires_boolean",
            ) from exc
        try:
            vertices, faces = self.tessellate(target)
            tool_vertices, tool_faces = self.tessellate(tool)
            first = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            second = trimesh.Trimesh(vertices=tool_vertices, faces=tool_faces, process=False)
            if operation == "union":
                result = trimesh_boolean.union([first, second])
            elif operation == "difference":
                result = trimesh_boolean.difference([first, second])
            else:
                result = trimesh_boolean.intersection([first, second])
        except Exception as exc:
            raise CADNotImplementedError(
                f"boolean {operation} failed: {exc}", code="unsupported_boolean"
            ) from exc
        return self._mesh_shape(result.vertices.tolist(), result.faces.tolist())

    @staticmethod
    def _mesh_shape(vertices: list[list[float]], faces: list[list[int]]) -> Shape:
        """Wrap raw ``vertices``/``faces`` into a ``mesh`` shape dict."""
        return {"kind": "mesh", "params": {"vertices": vertices, "faces": faces}}

    def create_mesh(self, vertices: list[list[float]], faces: list[list[int]]) -> Shape:
        """Create a ``mesh`` shape from explicit vertices and faces."""
        return self._mesh_shape(
            [list(vertex) for vertex in vertices],
            [list(face) for face in faces],
        )

    @staticmethod
    def _boxes_overlap(
        a_min: np.ndarray, a_max: np.ndarray, b_min: np.ndarray, b_max: np.ndarray
    ) -> bool:
        return all(a_max[i] > b_min[i] and b_max[i] > a_min[i] for i in range(3))

    @staticmethod
    def _box_contains(
        outer_min: np.ndarray, outer_max: np.ndarray, inner_min: np.ndarray, inner_max: np.ndarray
    ) -> bool:
        return all(inner_min[i] >= outer_min[i] and inner_max[i] <= outer_max[i] for i in range(3))

    # ------------------------------------------------------------------
    # Query / transform / mesh
    # ------------------------------------------------------------------

    def get_bbox(self, shape: Shape) -> dict[str, list[float]]:
        """Return ``{min: [x, y, z], max: [x, y, z]}`` bounding box."""
        kind = shape["kind"]
        params = shape["params"]
        if kind == "line":
            points = [params["start"], params["end"]]
        elif kind == "sphere":
            radius = params["radius"]
            center = np.array(params["center"], dtype=float)
            return {
                "min": (center - radius).tolist(),
                "max": (center + radius).tolist(),
            }
        elif kind in ("circle", "arc"):
            radius = params["radius"]
            cx, cy, cz = params["center"][:3]
            return {
                "min": [cx - radius, cy - radius, cz],
                "max": [cx + radius, cy + radius, cz],
            }
        elif kind == "rectangle":
            points = self._rectangle_corners(params)
        elif kind == "polygon":
            points = self._polygon_points(params)
        elif kind == "polyline":
            points = params["points"]
        elif kind == "box":
            points = self._box_corners(params)
        elif kind == "cylinder":
            points = self._cylinder_extents(params)
        elif kind == "cone":
            points = self._cone_extents(params)
        elif kind == "mesh":
            vertices = params["vertices"]
            if not vertices:
                return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}
            points = vertices
        else:
            raise CADNotImplementedError(
                f"get_bbox unsupported for {kind}", code="unsupported_kind"
            )
        return self._points_bbox(points)

    def transform(self, shape: Shape, matrix: Any) -> Shape:
        """Return a new shape with ``matrix`` (4x4) applied."""
        kind = shape["kind"]
        params = shape["params"]
        new_params = self._transform_params(kind, params, matrix)
        return {"kind": kind, "params": new_params}

    def tessellate(
        self, shape: Shape, deflection: float = 0.1
    ) -> tuple[list[list[float]], list[list[int]]]:
        """Return ``(vertices, faces)`` triangular mesh of ``shape``."""
        kind = shape["kind"]
        params = shape["params"]
        if kind == "box":
            return self._tessellate_box(params)
        if kind == "cylinder":
            return self._tessellate_cylinder(params)
        if kind == "sphere":
            return self._tessellate_sphere(params)
        if kind == "cone":
            return self._tessellate_cone(params)
        if kind == "mesh":
            return list(params["vertices"]), list(params["faces"])
        if kind in ("rectangle", "polygon", "polyline"):
            if kind == "rectangle":
                vertices = self._rectangle_corners(params)
            elif kind == "polygon":
                vertices = self._polygon_points(params)
            else:
                vertices = params["points"]
            faces: list[list[int]] = []
            if len(vertices) >= 3:
                for i in range(1, len(vertices) - 1):
                    faces.append([0, i, i + 1])
            return vertices, faces
        raise CADNotImplementedError(
            f"tessellate unsupported for {kind}", code="unsupported_kind"
        )

    def copy_shape(self, shape: Shape) -> Shape:
        """Return a deep copy of ``shape``."""
        import copy

        return copy.deepcopy(shape)

    def outline_points(self, shape: Shape) -> list[list[float]]:
        """Return the 2D polyline outline of a planar shape.

        Supported kinds: rectangle, polygon, polyline. Circles and arcs
        are handled directly by the DXF exporter.
        """
        kind = shape["kind"]
        params = shape["params"]
        if kind == "rectangle":
            return self._rectangle_corners(params)
        if kind == "polygon":
            return self._polygon_points(params)
        if kind == "polyline":
            return [list(point) for point in params["points"]]
        raise CADNotImplementedError(
            f"outline_points unsupported for {kind}", code="unsupported_kind"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_box_pair(target: Shape, tool: Shape, op: str) -> None:
        if target["kind"] != "box" or tool["kind"] != "box":
            raise CADNotImplementedError(
                f"boolean {op} is only supported for boxes by AnalyticKernel",
                code="unsupported_boolean",
            )

    @staticmethod
    def _empty_box() -> Shape:
        return {"kind": "box", "params": {
            "origin": [0.0, 0.0, 0.0],
            "dimensions": [0.0, 0.0, 0.0],
            "rotation": None,
        }}

    @staticmethod
    def _box_from_bbox(minimum: list[float], maximum: list[float]) -> Shape:
        return {
            "kind": "box",
            "params": {
                "origin": minimum,
                "dimensions": [
                    maximum[0] - minimum[0],
                    maximum[1] - minimum[1],
                    maximum[2] - minimum[2],
                ],
                "rotation": None,
            },
        }

    @staticmethod
    def _points_bbox(points: Sequence[Sequence[float]]) -> dict[str, list[float]]:
        array = np.array(points, dtype=float)
        minimum = np.min(array, axis=0)
        maximum = np.max(array, axis=0)
        return {
            "min": minimum.tolist(),
            "max": maximum.tolist(),
        }

    @staticmethod
    def _rotation_to_matrix(rotation: Sequence[float]) -> list[list[float]]:
        from cad_mcp_server.core.transform import compose, rotation_x, rotation_y, rotation_z

        if len(rotation) == 3:
            matrix = compose(
                rotation_x(rotation[0]), rotation_y(rotation[1]), rotation_z(rotation[2])
            )
        elif len(rotation) == 1:
            matrix = rotation_z(rotation[0])
        else:
            raise CADValidationError("rotation must have 1 or 3 angles", code="invalid_rotation")
        result = matrix[:3, :3].tolist()
        return [[float(value) for value in row] for row in result]

    @staticmethod
    def _rotate_vector(
        matrix_3x3: Sequence[Sequence[float]], vector: Sequence[float]
    ) -> list[float]:
        return list(np.dot(np.array(matrix_3x3, dtype=float), np.array(vector, dtype=float)))

    def _rectangle_corners(self, params: dict[str, Any]) -> list[list[float]]:
        origin = np.array(params["origin"][:2], dtype=float)
        width, height, rotation = params["width"], params["height"], params["rotation"]
        half = np.array([width / 2.0, height / 2.0])
        center = origin + half
        radians = np.radians(rotation)
        c, s = np.cos(radians), np.sin(radians)
        rot = np.array([[c, -s], [s, c]])
        corners = [
            center + rot @ np.array([-width / 2.0, -height / 2.0]),
            center + rot @ np.array([width / 2.0, -height / 2.0]),
            center + rot @ np.array([width / 2.0, height / 2.0]),
            center + rot @ np.array([-width / 2.0, height / 2.0]),
        ]
        z = float(params["origin"][2]) if len(params["origin"]) > 2 else 0.0
        return [[float(corner[0]), float(corner[1]), z] for corner in corners]

    def _polygon_points(self, params: dict[str, Any]) -> list[list[float]]:
        center = np.array(params["center"][:2], dtype=float)
        radius, sides, rotation = params["radius"], params["sides"], params["rotation"]
        angles = np.radians(rotation) + np.radians(np.linspace(0.0, 360.0, sides, endpoint=False))
        z = float(params["center"][2]) if len(params["center"]) > 2 else 0.0
        points = [
            [float(center[0] + radius * np.cos(a)), float(center[1] + radius * np.sin(a)), z]
            for a in angles
        ]
        return points

    def _box_corners(self, params: dict[str, Any]) -> list[list[float]]:
        origin = np.array(params["origin"], dtype=float)
        dims = np.array(params["dimensions"], dtype=float)
        rotation = params.get("rotation")
        corners = []
        for i in range(2):
            for j in range(2):
                for k in range(2):
                    local = np.array([i * dims[0], j * dims[1], k * dims[2]])
                    if rotation is not None:
                        local = np.dot(np.array(rotation, dtype=float), local)
                    corners.append((origin + local).tolist())
        return corners

    def _cylinder_extents(self, params: dict[str, Any]) -> list[list[float]]:
        origin = np.array(params["origin"], dtype=float)
        axis = np.array(params["axis"], dtype=float)
        norm = np.linalg.norm(axis)
        if norm == 0:
            axis = np.array([0.0, 0.0, 1.0])
            norm = 1.0
        axis = axis / norm
        top = origin + axis * params["height"]
        radius = params["radius"]
        points = [
            origin + np.array([-radius, -radius, 0.0]),
            origin + np.array([radius, radius, 0.0]),
            top + np.array([-radius, -radius, 0.0]),
            top + np.array([radius, radius, 0.0]),
        ]
        return [point.tolist() for point in points]

    def _cone_extents(self, params: dict[str, Any]) -> list[list[float]]:
        origin = np.array(params["origin"], dtype=float)
        top = origin + np.array([0.0, 0.0, params["height"]])
        radius = max(params["radius_bottom"], params["radius_top"])
        points = [
            origin + np.array([-radius, -radius, 0.0]),
            origin + np.array([radius, radius, 0.0]),
            top + np.array([-radius, -radius, 0.0]),
            top + np.array([radius, radius, 0.0]),
        ]
        return [point.tolist() for point in points]

    def _transform_params(self, kind: str, params: dict[str, Any], matrix: Any) -> dict[str, Any]:
        from cad_mcp_server.core.transform import apply_point, apply_points, uniform_scale

        scale_factor = uniform_scale(matrix)
        new_params = dict(params)
        if kind == "line":
            new_params["start"] = apply_point(matrix, params["start"])
            new_params["end"] = apply_point(matrix, params["end"])
        elif kind == "polyline":
            new_params["points"] = apply_points(matrix, params["points"])
        elif kind in ("circle", "arc") or kind == "sphere":
            new_params["center"] = apply_point(matrix, params["center"])
            new_params["radius"] = params["radius"] * scale_factor
        elif kind == "rectangle":
            corners = self._rectangle_corners(params)
            transformed = apply_points(matrix, corners)
            xs = [p[0] for p in transformed]
            ys = [p[1] for p in transformed]
            new_params["origin"] = [min(xs), min(ys), transformed[0][2]]
            new_params["width"] = max(xs) - min(xs)
            new_params["height"] = max(ys) - min(ys)
            new_params["rotation"] = 0.0
        elif kind == "polygon":
            points = apply_points(matrix, self._polygon_points(params))
            center = np.mean(points, axis=0)
            radius = np.mean([np.linalg.norm(np.array(p) - center) for p in points])
            new_params["center"] = center.tolist()
            new_params["radius"] = float(radius)
            new_params["rotation"] = params["rotation"]
        elif kind == "box":
            new_params["origin"] = apply_point(matrix, params["origin"])
            new_params["dimensions"] = [value * scale_factor for value in params["dimensions"]]
            rotation = params.get("rotation")
            if rotation is not None:
                from cad_mcp_server.core.transform import rotation_part

                linear = rotation_part(matrix)[:3, :3]
                new_rotation = np.dot(linear, np.array(rotation, dtype=float))
                new_params["rotation"] = new_rotation.tolist()
        elif kind == "cylinder":
            new_params["origin"] = apply_point(matrix, params["origin"])
            new_params["radius"] = params["radius"] * scale_factor
            new_params["height"] = params["height"] * scale_factor
        elif kind == "cone":
            new_params["origin"] = apply_point(matrix, params["origin"])
            new_params["radius_bottom"] = params["radius_bottom"] * scale_factor
            new_params["radius_top"] = params["radius_top"] * scale_factor
            new_params["height"] = params["height"] * scale_factor
        elif kind == "mesh":
            new_params["vertices"] = apply_points(matrix, params["vertices"])
        else:
            raise CADNotImplementedError(
                f"transform unsupported for {kind}", code="unsupported_kind"
            )
        return new_params

    # ------------------------------------------------------------------
    # Meshing helpers
    # ------------------------------------------------------------------

    def _tessellate_box(self, params: dict[str, Any]) -> tuple[list[list[float]], list[list[int]]]:
        corners = self._box_corners(params)
        faces = [
            [0, 1, 3], [0, 3, 2],  # x-min
            [4, 7, 5], [6, 7, 4],  # x-max
            [0, 4, 5], [0, 5, 1],  # y-min
            [1, 5, 7], [1, 7, 3],  # z-max
            [2, 3, 7], [2, 7, 6],  # y-max
            [0, 2, 6], [0, 6, 4],  # z-min
        ]
        return corners, faces

    def _tessellate_cylinder(
        self, params: dict[str, Any]
    ) -> tuple[list[list[float]], list[list[int]]]:
        origin = np.array(params["origin"], dtype=float)
        axis = np.array(params["axis"], dtype=float)
        norm = np.linalg.norm(axis)
        axis = axis / norm if norm else np.array([0.0, 0.0, 1.0])
        radius, height = params["radius"], params["height"]
        z_base = origin.copy()
        z_top = origin + axis * height
        segments = 24
        # Build two circles in the XY plane, then offset along axis direction.
        base = np.zeros((segments, 3))
        angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
        base[:, 0] = np.cos(angles)
        base[:, 1] = np.sin(angles)
        base *= radius
        # Rotate the local XY circle so its normal aligns with axis.
        rot = _align_z_rotation(axis)
        base = base @ rot.T
        vertices = [
            (z_base + point).tolist() for point in base
        ] + [
            (z_top + point).tolist() for point in base
        ]
        faces: list[list[int]] = []
        for i in range(segments):
            j = (i + 1) % segments
            faces.append([i, j, segments + j])
            faces.append([i, segments + j, segments + i])
        faces.append(list(range(segments))[::-1])  # bottom cap
        faces.append([segments + i for i in range(segments)])  # top cap
        # Fan triangulate caps.
        bottom_face = faces.pop()
        top_face = faces.pop()
        bottom_center = len(vertices)
        top_center = bottom_center + 1
        vertices.append((z_base - axis * 0.0).tolist())  # bottom centre
        vertices.append((z_top + axis * 0.0).tolist())  # top centre
        for i in range(segments):
            j = (i + 1) % segments
            faces.append([bottom_face[i], bottom_face[j], bottom_center])
            faces.append([top_face[i], top_face[j], top_center])
        return vertices, faces

    def _tessellate_sphere(
        self, params: dict[str, Any]
    ) -> tuple[list[list[float]], list[list[int]]]:
        center = np.array(params["center"], dtype=float)
        radius = params["radius"]
        stacks, slices_ = 16, 24
        vertices: list[list[float]] = [list(center + np.array([0.0, 0.0, radius]))]
        rings: list[list[int]] = []
        for i in range(1, stacks):
            phi = np.pi * i / stacks
            ring: list[int] = []
            for j in range(slices_):
                theta = 2.0 * np.pi * j / slices_
                x = radius * np.sin(phi) * np.cos(theta)
                y = radius * np.sin(phi) * np.sin(theta)
                z = radius * np.cos(phi)
                ring.append(len(vertices))
                vertices.append((center + np.array([x, y, z])).tolist())
            rings.append(ring)
        south_pole = len(vertices)
        vertices.append((center - np.array([0.0, 0.0, radius])).tolist())
        faces: list[list[int]] = []
        # Cap at the north pole.
        top_ring = rings[0]
        for j in range(slices_):
            faces.append([top_ring[j], top_ring[(j + 1) % slices_], 0])
        # Quad strips between rings.
        for i in range(len(rings) - 1):
            lower, upper = rings[i], rings[i + 1]
            for j in range(slices_):
                j2 = (j + 1) % slices_
                faces.append([lower[j], upper[j2], lower[j2]])
                faces.append([lower[j], upper[j], upper[j2]])
        # Cap at the south pole.
        bottom_ring = rings[-1]
        for j in range(slices_):
            faces.append(
                [bottom_ring[(j + 1) % slices_], bottom_ring[j], south_pole]
            )
        return vertices, faces

    def _tessellate_cone(self, params: dict[str, Any]) -> tuple[list[list[float]], list[list[int]]]:
        origin = np.array(params["origin"], dtype=float)
        top = origin + np.array([0.0, 0.0, params["height"]])
        radius_bottom = params["radius_bottom"]
        radius_top = params["radius_top"]
        segments = 24
        angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
        bottom = np.array(
            [[np.cos(a) * radius_bottom, np.sin(a) * radius_bottom, 0.0] for a in angles]
        )
        vertices = [(origin + point).tolist() for point in bottom]
        faces: list[list[int]] = []
        bottom_center = len(vertices)
        vertices.append(origin.tolist())
        if radius_top > 0:
            upper = np.array(
                [
                    [np.cos(a) * radius_top, np.sin(a) * radius_top, params["height"]]
                    for a in angles
                ]
            )
            upper_base = len(vertices)
            vertices.extend((top + point).tolist() for point in upper)
            top_center = len(vertices)
            vertices.append(top.tolist())
            for i in range(segments):
                j = (i + 1) % segments
                faces.append([i, j, upper_base + j])
                faces.append([i, upper_base + j, upper_base + i])
                faces.append([upper_base + i, upper_base + j, top_center])
                faces.append([j, i, bottom_center])
        else:
            apex = len(vertices)
            vertices.append(top.tolist())
            for i in range(segments):
                j = (i + 1) % segments
                faces.append([i, j, apex])
                faces.append([j, i, bottom_center])
        return vertices, faces


def _bbox_arrays(shape: Shape) -> tuple[np.ndarray, np.ndarray]:
    kernel = AnalyticKernel()
    bbox = kernel.get_bbox(shape)
    return np.array(bbox["min"], dtype=float), np.array(bbox["max"], dtype=float)


def _align_z_rotation(axis: np.ndarray) -> np.ndarray:
    """Return a rotation matrix that maps Z onto ``axis``."""
    z = np.array([0.0, 0.0, 1.0])
    axis = np.asarray(axis, dtype=float)
    norm = np.linalg.norm(axis)
    if norm == 0:
        return np.eye(3)
    axis = axis / norm
    v = np.cross(z, axis)
    c = np.dot(z, axis)
    if np.linalg.norm(v) < 1e-12:
        if c < 0:
            return np.diag([-1.0, -1.0, 1.0])
        return np.eye(3)
    skew = np.array([
        [0.0, -v[2], v[1]],
        [v[2], 0.0, -v[0]],
        [-v[1], v[0], 0.0],
    ])
    result = np.eye(3) + skew + skew @ skew * (1.0 / (1.0 + c))
    return result  # type: ignore[no-any-return]


def get_kernel(runtime: str | None = None) -> CADKernel:
    """Return the kernel configured by ``CAD_RUNTIME`` (default analytic)."""
    selected = (runtime or get_settings().runtime or "analytic").lower().strip()
    if selected in ("analytic", "none", "default"):
        return AnalyticKernel()
    if selected == "ocp":
        return _load_backend("cad_mcp_server.core.backends.occt", "OCCTKernel", "cadquery")
    if selected == "freecad":
        return _load_backend("cad_mcp_server.core.backends.freecad", "FreeCADKernel", "FreeCAD")
    raise CADValidationError(
        f"Unknown CAD_RUNTIME {selected!r}. Supported: analytic, ocp, freecad",
        code="invalid_runtime",
    )


def _load_backend(module_path: str, class_name: str, package: str) -> CADKernel:
    try:
        module = __import__(module_path, fromlist=[class_name])
    except ImportError as exc:
        raise CADValidationError(
            (
                f"Backend {package} is not installed; run `pip install -e '.[occ]'` "
                f"or install {package}"
            ),
            code="backend_unavailable",
        ) from exc
    try:
        backend = getattr(module, class_name)()
        return backend  # type: ignore[no-any-return]
    except CADNotImplementedError as exc:
        raise CADValidationError(str(exc), code="backend_unavailable") from exc
