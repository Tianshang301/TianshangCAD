"""OCCT backend based on ``cadquery``/``ocp`` (optional extra).

The OCCT kernel computes exact NURBS geometry through the OpenCascade
bindings (``cadquery``), then returns JSON-serialisable shape dicts
mirroring :class:`~tianshangcad.core.kernel.AnalyticKernel` so the
entity/document layer works unchanged. Booleans use the exact OCC BRep
algorithm (rather than the analytic kernel's mesh fallback), and STEP /
IGES export writes true BREP through the OCCT writers.

Requires ``pip install -e '.[occ]'``. When cadquery is absent, every
method raises :class:`CADNotImplementedError` with code
``requires_occ`` so callers can degrade gracefully (the default
analytic kernel remains the fallback).

Spike 2 findings (2026-08-03): OCC create/boolean/sweep/loft/export all
verified. STEP export->reimport and IGES export->reimport are
geometry-consistent (volumes match exactly). cadquery 2.4 ships cp312
wheels but requires numpy <2 (nptyping uses removed ``np.bool8`` aliases);
its exporter does not support IGES, so IGES uses ``OCP.IGESControl``
directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

import numpy as np

from tianshangcad.core.kernel import CADKernel, Shape
from tianshangcad.utils.errors import CADNotImplementedError, CADValidationError

Point = Sequence[float]


class OCCTKernel(CADKernel):
    """CAD kernel backed by the OCCT bindings (cadquery).

    Requires ``pip install -e '.[occ]'``. Returns the same JSON-safe
    shape dicts as :class:`AnalyticKernel`; booleans of solids and STEP /
    IGES export use the exact OCCT geometry path.
    """

    def __init__(self) -> None:
        """Initialise the OCCT kernel by importing ``cadquery``."""
        try:
            import cadquery  # type: ignore[import-not-found, unused-ignore]
            from OCP.BRepGProp import BRepGProp  # type: ignore[import-not-found]
            from OCP.GProp import GProp_GProps  # type: ignore[import-not-found]
        except ImportError as exc:
            raise CADNotImplementedError(
                "OCCT backend requires cadquery; run `pip install -e '.[occ]'`",
                code="backend_unavailable",
            ) from exc
        self._cq = cadquery
        self._brep = BRepGProp
        self._gprops = GProp_GProps

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _err(message: str = "OCCT operation") -> CADNotImplementedError:
        """Return a ``requires_occ`` error for fallback reporting."""
        return CADNotImplementedError(
            f"OCCT {message} requires cadquery; run `pip install -e '.[occ]'`",
            code="requires_occ",
        )

    def _workplane(self, kind: str, params: dict[str, Any]) -> Any:
        """Return an ``Solid``/``Workplane`` for a primitive shape dict."""
        cq = self._cq
        if kind == "line":
            start = params["start"]
            end = params["end"]
            line = cq.Edge.makeLine(cq.Vector(*start[:3]), cq.Vector(*end[:3]))
            return line
        if kind == "circle":
            center = params["center"]
            return (
                cq.Workplane("XY")
                .circle(params["radius"])
                .translate((center[0], center[1], center[2]))
            )
        if kind == "arc":
            center = params["center"]
            radius = params["radius"]
            start_angle = params["start_angle"]
            end_angle = params["end_angle"]
            s = np.radians(start_angle)
            e = np.radians(end_angle)
            a = cq.Vector(center[0] + radius * np.cos(s), center[1] + radius * np.sin(s), center[2])
            b = cq.Vector(center[0] + radius * np.cos(e), center[1] + radius * np.sin(e), center[2])
            c = cq.Vector(*center[:3])
            return cq.Edge.makeThreePointArc(a, c, b)
        if kind == "rectangle":
            origin = params["origin"]
            w, h = params["width"], params["height"]
            return (
                cq.Workplane("XY")
                .rect(w, h)
                .translate((origin[0] + w / 2.0, origin[1] + h / 2.0, origin[2]))
                .rotate((0, 0, 0), (0, 0, 1), params["rotation"])
            )
        if kind == "polygon":
            center = params["center"]
            return (
                cq.Workplane("XY")
                .polygon(params["sides"], params["radius"])
                .translate((center[0], center[1], center[2]))
                .rotate((0, 0, 0), (0, 0, 1), params["rotation"])
            )
        if kind == "polyline":
            points = [cq.Vector(*p[:3]) for p in params["points"]]
            polyline = cq.Workplane("XY").polyline(points)
            if params.get("closed"):
                polyline = polyline.close()
            return polyline
        if kind == "box":
            origin = params["origin"]
            dims = params["dimensions"]
            wp = (
                cq.Workplane("XY")
                .box(dims[0], dims[1], dims[2])
                .translate(
                    (
                        origin[0] + dims[0] / 2.0,
                        origin[1] + dims[1] / 2.0,
                        origin[2] + dims[2] / 2.0,
                    )
                )
            )
            rotation = params.get("rotation")
            if rotation is not None:
                matrix = np.asarray(rotation, dtype=float)
                wp = wp.val().transformGeometry(_matrix_3x3(matrix))
            return wp
        if kind == "cylinder":
            origin = params["origin"]
            radius, height = params["radius"], params["height"]
            axis = params.get("axis", (0, 0, 1))
            ax = np.asarray(axis, dtype=float)
            norm = np.linalg.norm(ax)
            ax = ax / norm if norm else np.array([0.0, 0.0, 1.0])
            # cadquery centers the cylinder on the workplane; offset so the
            # base sits at ``origin`` (matching AnalyticKernel semantics).
            center = (np.array(origin[:3]) + ax * (height / 2.0)).tolist()
            wp = (
                cq.Workplane("XY")
                .cylinder(height, radius)
                .translate((center[0], center[1], center[2]))
            )
            if not np.allclose(ax, [0.0, 0.0, 1.0]):
                rot = _align_z_rotation(ax)
                wp = wp.val().transformGeometry(_matrix_3x3(rot)).toWorkplane()
            return wp
        if kind == "sphere":
            center = params["center"]
            return (
                cq.Workplane("XY")
                .sphere(params["radius"])
                .translate((center[0], center[1], center[2]))
            )
        if kind == "cone":
            origin = params["origin"]
            r_b, r_t, height = (
                params["radius_bottom"],
                params["radius_top"],
                params["height"],
            )
            wp = cq.Workplane("XY").circle(r_b).workplane(offset=height).circle(r_t).loft()
            return wp.translate((origin[0], origin[1], origin[2]))
        if kind == "mesh":
            return self._cq.Workplane("XY")
        raise CADNotImplementedError(f"OCCT create unsupported for {kind}", code="unsupported_kind")

    def _solid(self, shape: Shape) -> Any:
        """Return a cadquery ``Solid``/``Shape`` for a shape dict."""
        wp = self._workplane(shape["kind"], shape["params"])
        if wp is None:
            raise CADNotImplementedError(
                f"OCCT unsupported shape {shape['kind']}", code="unsupported_kind"
            )
        return wp

    def _val(self, wp: Any) -> Any:
        """Return the cadquery Shape value of a Workplane/Edge/etc."""
        return wp.val() if hasattr(wp, "val") else wp

    def _mesh_dict(self, solid: Any) -> Shape:
        """Tessellate an OCC solid into a ``mesh`` shape dict."""
        vertices, faces = solid.tessellate(0.1)
        verts = [[float(v.x), float(v.y), float(v.z)] for v in vertices]
        return {
            "kind": "mesh",
            "params": {"vertices": verts, "faces": [list(f) for f in faces]},
        }

    def _volume(self, shape: Any) -> float:
        props = self._gprops()
        self._brep.VolumeProperties_s(shape.wrapped, props)
        return float(props.Mass())

    # ------------------------------------------------------------------
    # Primitives
    # ------------------------------------------------------------------

    def create_line(self, start: Point, end: Point) -> Shape:
        """Create a line segment from ``start`` to ``end``."""
        return {
            "kind": "line",
            "params": {
                "start": [float(v) for v in start[:3]],
                "end": [float(v) for v in end[:3]],
            },
        }

    def create_circle(self, center: Point, radius: float) -> Shape:
        """Create a circle with the given centre and radius."""
        if radius <= 0:
            raise CADValidationError("radius must be > 0", code="invalid_radius")
        return {
            "kind": "circle",
            "params": {"center": [float(v) for v in center[:3]], "radius": float(radius)},
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
                "center": [float(v) for v in center[:3]],
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
                "origin": [float(v) for v in origin[:3]],
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
                "center": [float(v) for v in center[:3]],
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
                "points": [[float(v) for v in p[:3]] for p in points],
                "closed": bool(closed),
            },
        }

    def create_box(
        self,
        origin: Point,
        dimensions: Point,
        rotation: Sequence[float] | Sequence[Sequence[float]] | None = None,
    ) -> Shape:
        """Create an axis-aligned (or rotated) box."""
        dims = [float(v) for v in dimensions[:3]]
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
                from tianshangcad.core.transform import (
                    compose,
                    rotation_x,
                    rotation_y,
                    rotation_z,
                )

                angles = cast(Sequence[float], rotation_list)
                matrix = compose(
                    rotation_x(angles[0]),
                    rotation_y(angles[1]) if len(angles) > 1 else np.eye(4),
                    rotation_z(angles[-1]),
                )
                rotation_matrix = matrix[:3, :3].tolist()
        return {
            "kind": "box",
            "params": {
                "origin": [float(v) for v in origin[:3]],
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
                "origin": [float(v) for v in origin[:3]],
                "radius": float(radius),
                "height": float(height),
                "axis": [float(v) for v in axis[:3]],
            },
        }

    def create_sphere(self, center: Point, radius: float) -> Shape:
        """Create a sphere."""
        if radius <= 0:
            raise CADValidationError("radius must be > 0", code="invalid_radius")
        return {
            "kind": "sphere",
            "params": {"center": [float(v) for v in center[:3]], "radius": float(radius)},
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
                "origin": [float(v) for v in origin[:3]],
                "radius_bottom": float(radius_bottom),
                "radius_top": float(radius_top),
                "height": float(height),
            },
        }

    def create_mesh(self, vertices: list[list[float]], faces: list[list[int]]) -> Shape:
        """Create a ``mesh`` shape from explicit vertices and faces."""
        return {
            "kind": "mesh",
            "params": {
                "vertices": [[float(v) for v in vertex] for vertex in vertices],
                "faces": [[int(i) for i in face] for face in faces],
            },
        }

    # ------------------------------------------------------------------
    # Boolean operations (exact OCC BRep)
    # ------------------------------------------------------------------

    def _boolean(self, operation: str, target: Shape, tool: Shape) -> Shape:
        try:
            target_solid = self._solid(target)
            tool_solid = self._solid(tool)
            if operation == "union":
                result = target_solid.union(tool_solid)
            elif operation == "subtract":
                result = target_solid.cut(tool_solid)
            else:
                result = target_solid.intersect(tool_solid)
        except Exception as exc:
            raise CADNotImplementedError(
                f"OCCT boolean {operation} failed: {exc}", code="unsupported_boolean"
            ) from exc
        result_val = self._val(result)
        if not result_val.isValid():
            raise CADNotImplementedError(
                f"OCCT boolean {operation} produced an invalid shape",
                code="degenerate_boolean",
            )
        return self._mesh_dict(result_val)

    def boolean_union(self, target: Shape, tool: Shape) -> Shape:
        """Boolean union using the exact OCCT BRep algorithm."""
        return self._boolean("union", target, tool)

    def boolean_subtract(self, target: Shape, tool: Shape) -> Shape:
        """Boolean subtraction using the exact OCCT BRep algorithm."""
        return self._boolean("subtract", target, tool)

    def boolean_intersect(self, target: Shape, tool: Shape) -> Shape:
        """Boolean intersection using the exact OCCT BRep algorithm."""
        return self._boolean("intersect", target, tool)

    # ------------------------------------------------------------------
    # Query / transform / mesh
    # ------------------------------------------------------------------

    def get_bbox(self, shape: Shape) -> dict[str, list[float]]:
        """Return ``{min: [x, y, z], max: [x, y, z]}`` bounding box."""
        if shape["kind"] == "mesh":
            vertices = shape["params"]["vertices"]
            if not vertices:
                return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}
            arr = np.array(vertices, dtype=float)
            return {
                "min": np.min(arr, axis=0).tolist(),
                "max": np.max(arr, axis=0).tolist(),
            }
        solid = self._val(self._solid(shape))
        bb = solid.BoundingBox()
        return {
            "min": [float(bb.xmin), float(bb.ymin), float(bb.zmin)],
            "max": [float(bb.xmax), float(bb.ymax), float(bb.zmax)],
        }

    def transform(self, shape: Shape, matrix: Any) -> Shape:
        """Return a new shape with ``matrix`` (4x4) applied."""
        from tianshangcad.core.transform import apply_point, uniform_scale

        scale = uniform_scale(matrix)
        kind = shape["kind"]
        params = shape["params"]
        new_params: dict[str, Any] = {}
        if kind == "line":
            new_params["start"] = apply_point(matrix, params["start"])
            new_params["end"] = apply_point(matrix, params["end"])
        elif kind == "polyline":
            new_params["points"] = [apply_point(matrix, p) for p in params["points"]]
            new_params["closed"] = params.get("closed", False)
        elif kind in ("circle", "arc", "sphere"):
            new_params["center"] = apply_point(matrix, params["center"])
            new_params["radius"] = params["radius"] * scale
            if kind == "arc":
                new_params["start_angle"] = params["start_angle"]
                new_params["end_angle"] = params["end_angle"]
        elif kind == "rectangle":
            corners = self._rectangle_corners(params)
            transformed = [apply_point(matrix, c) for c in corners]
            xs = [p[0] for p in transformed]
            ys = [p[1] for p in transformed]
            new_params["origin"] = [min(xs), min(ys), transformed[0][2]]
            new_params["width"] = max(xs) - min(xs)
            new_params["height"] = max(ys) - min(ys)
            new_params["rotation"] = 0.0
        elif kind == "polygon":
            points = [apply_point(matrix, p) for p in self._polygon_points(params)]
            center = np.mean(points, axis=0)
            radius = np.mean([np.linalg.norm(np.array(p) - center) for p in points])
            new_params["center"] = center.tolist()
            new_params["radius"] = float(radius)
            new_params["sides"] = params["sides"]
            new_params["rotation"] = params["rotation"]
        elif kind == "box":
            new_params["origin"] = apply_point(matrix, params["origin"])
            new_params["dimensions"] = [v * scale for v in params["dimensions"]]
            rotation = params.get("rotation")
            if rotation is not None:
                from tianshangcad.core.transform import rotation_part

                new_rotation = np.dot(rotation_part(matrix)[:3, :3], np.array(rotation))
                new_params["rotation"] = new_rotation.tolist()
            else:
                new_params["rotation"] = None
        elif kind == "cylinder":
            new_params["origin"] = apply_point(matrix, params["origin"])
            new_params["radius"] = params["radius"] * scale
            new_params["height"] = params["height"] * scale
            new_params["axis"] = params["axis"]
        elif kind == "cone":
            new_params["origin"] = apply_point(matrix, params["origin"])
            new_params["radius_bottom"] = params["radius_bottom"] * scale
            new_params["radius_top"] = params["radius_top"] * scale
            new_params["height"] = params["height"] * scale
        elif kind == "mesh":
            new_params["vertices"] = [apply_point(matrix, v) for v in params["vertices"]]
            new_params["faces"] = list(params["faces"])
        else:
            raise CADNotImplementedError(
                f"OCCT transform unsupported for {kind}", code="unsupported_kind"
            )
        return {"kind": kind, "params": new_params}

    def tessellate(
        self, shape: Shape, deflection: float = 0.1
    ) -> tuple[list[list[float]], list[list[int]]]:
        """Return ``(vertices, faces)`` triangular mesh of ``shape``."""
        kind = shape["kind"]
        if kind == "mesh":
            return list(shape["params"]["vertices"]), list(shape["params"]["faces"])
        solid = self._val(self._solid(shape))
        vertices, faces = solid.tessellate(deflection)
        return (
            [[float(v.x), float(v.y), float(v.z)] for v in vertices],
            [list(f) for f in faces],
        )

    def copy_shape(self, shape: Shape) -> Shape:
        """Return a deep copy of ``shape``."""
        import copy

        return copy.deepcopy(shape)

    # ------------------------------------------------------------------
    # Phase 8 feature primitives (sweep / loft) — Spike 2 validation
    # ------------------------------------------------------------------

    def sweep(self, profile: Shape, path: list[Point]) -> Shape:
        """Sweep a 2D profile circle/rectangle along a polyline path.

        Returns a ``mesh`` shape dict (tessellated OCC result).
        """
        cq = self._cq
        if profile["kind"] != "circle":
            raise CADNotImplementedError(
                "OCCT sweep currently supports circle profiles",
                code="unsupported_feature",
            )
        radius = profile["params"]["radius"]
        path_points = [cq.Vector(*p[:3]) for p in path]
        if len(path_points) < 2:
            raise CADValidationError("sweep path needs at least 2 points", code="invalid_path")
        # Sweep the circle profile along the polygon wire.
        sketch_plane = cq.Workplane("YZ").circle(radius)
        wire = cq.Wire.makePolygon(path_points)
        result = sketch_plane.sweep(wire, isFrenet=True)
        return self._mesh_dict(result.val())

    def loft(self, profiles: list[Shape], loft_sections: list[Point] | None = None) -> Shape:
        """Loft between stacked rectangle/circle profiles.

        Returns a ``mesh`` shape dict (tessellated OCC result).
        """
        if len(profiles) < 2:
            raise CADValidationError("loft needs at least 2 profiles", code="invalid_profiles")
        workplane: Any = None
        for index, profile in enumerate(profiles):
            offset = float(loft_sections[index][2]) if loft_sections else float(index) * 10.0
            if workplane is None:
                workplane = self._profile_workplane(profile, offset)
            else:
                workplane = workplane.workplane(offset=offset)
                workplane = self._profile_on(workplane, profile)
        result = workplane.loft()
        return self._mesh_dict(result.val())

    def fillet(self, shape: Shape, radius: float) -> Shape:
        """Blend all edges of ``shape`` with a fillet of ``radius``.

        Returns a ``mesh`` shape dict (tessellated OCC result). Failing
        geometry (e.g. radius larger than an edge) raises a friendly
        ``degenerate_feature`` error.
        """
        if radius <= 0:
            raise CADValidationError("fillet radius must be > 0", code="invalid_radius")
        wp = self._workplane(shape["kind"], shape["params"])
        try:
            result = wp.fillet(radius)
        except Exception as exc:
            raise CADNotImplementedError(
                f"OCCT fillet failed: {exc}", code="degenerate_feature"
            ) from exc
        return self._mesh_dict(self._val(result))

    def chamfer(self, shape: Shape, size: float) -> Shape:
        """Cut all edges of ``shape`` with a chamfer of ``size``."""
        if size <= 0:
            raise CADValidationError("chamfer size must be > 0", code="invalid_size")
        wp = self._workplane(shape["kind"], shape["params"])
        try:
            result = wp.chamfer(size)
        except Exception as exc:
            raise CADNotImplementedError(
                f"OCCT chamfer failed: {exc}", code="degenerate_feature"
            ) from exc
        return self._mesh_dict(self._val(result))

    # ------------------------------------------------------------------
    # STEP / IGES export (true OCC BREP)
    # ------------------------------------------------------------------

    def export_step(self, shape: Shape, filepath: str) -> None:
        """Write ``shape`` to a STEP file using the OCC STEPControl writer."""
        cq = self._cq
        solid = self._val(self._solid(shape))
        cq.exporters.export(solid, filepath, exportType="STEP")

    def export_iges(self, shape: Shape, filepath: str) -> None:
        """Write ``shape`` to an IGES file using the OCP IGESControl writer."""
        from OCP.IGESControl import IGESControl_Writer  # type: ignore[import-not-found]

        solid = self._val(self._solid(shape))
        writer = IGESControl_Writer()
        writer.AddShape(solid.wrapped)
        writer.Write(filepath)

    def import_step(self, filepath: str) -> Shape:
        """Import a STEP file and return its ``mesh`` shape dict."""
        cq = self._cq
        result = cq.importers.importStep(filepath)
        return self._mesh_dict(self._val(result))

    # ------------------------------------------------------------------
    # Profile helpers for loft
    # ------------------------------------------------------------------

    def _profile_workplane(self, profile: Shape, z: float) -> Any:
        cq = self._cq
        kind = profile["kind"]
        params = profile["params"]
        if kind == "circle":
            return cq.Workplane("XY").circle(params["radius"]).workplane(offset=z)
        if kind == "rectangle":
            return cq.Workplane("XY").rect(params["width"], params["height"]).workplane(offset=z)
        raise CADNotImplementedError(
            f"OCCT loft profile {kind} unsupported", code="unsupported_feature"
        )

    def _profile_on(self, workplane: Any, profile: Shape) -> Any:
        params = profile["params"]
        kind = profile["kind"]
        if kind == "circle":
            return workplane.circle(params["radius"])
        if kind == "rectangle":
            return workplane.rect(params["width"], params["height"])
        raise CADNotImplementedError(
            f"OCCT loft profile {kind} unsupported", code="unsupported_feature"
        )

    # ------------------------------------------------------------------
    # Polygon / rectangle corner helpers (mirror AnalyticKernel)
    # ------------------------------------------------------------------

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
        return [
            [float(center[0] + radius * np.cos(a)), float(center[1] + radius * np.sin(a)), z]
            for a in angles
        ]

    def outline_points(self, shape: Shape) -> list[list[float]]:
        """Return the 2D polyline outline of a planar shape."""
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


def _matrix_3x3(matrix: np.ndarray[Any, Any]) -> Any:
    """Build a cadquery transform matrix from a 3x3 rotation."""
    import cadquery as cq

    m = np.eye(4)
    m[:3, :3] = matrix
    return cq.Matrix(
        [
            [float(m[0][0]), float(m[0][1]), float(m[0][2]), float(m[0][3])],
            [float(m[1][0]), float(m[1][1]), float(m[1][2]), float(m[1][3])],
            [float(m[2][0]), float(m[2][1]), float(m[2][2]), float(m[2][3])],
            [float(m[3][0]), float(m[3][1]), float(m[3][2]), float(m[3][3])],
        ]
    )


def _align_z_rotation(axis: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Return a rotation matrix that maps Z onto ``axis`` (Rodrigues)."""
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
    skew = np.array(
        [
            [0.0, -v[2], v[1]],
            [v[2], 0.0, -v[0]],
            [-v[1], v[0], 0.0],
        ]
    )
    result = np.eye(3) + skew + skew @ skew * (1.0 / (1.0 + c))
    return result  # type: ignore[no-any-return]
