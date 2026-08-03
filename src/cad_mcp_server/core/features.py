"""Parametric feature modelling.

Features create new entities from existing ones. Sweep and loft use the
OCCT backend (``[occ]`` extra) for full generality, with an analytic
fallback for straight sweeps (circle -> cylinder, rectangle -> box) and
stacked-cone lofts (concentric circles -> cone). Fillet and chamfer are
exact only on the OCCT path; the analytic kernel raises a friendly
``requires_occ`` error (see Spike 2: NURBS-style features report
``requires_occ`` and the analytic kernel remains the default). Linear,
circular and mirror patterns are pure rigid transforms and therefore work
on every kernel.

Feature parameters may be driven by document variables: callers pass the
resolved values, and the CLI layer performs ``{name}`` interpolation
before calling in.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from cad_mcp_server.core.entity import EntityManager
from cad_mcp_server.core.kernel import CADKernel, Shape
from cad_mcp_server.core.transform import compose, translation
from cad_mcp_server.utils.errors import CADNotImplementedError, CADValidationError

Point = Sequence[float]

_TOL = 1e-9


def _unit(vector: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Return the unit vector of ``vector`` or raise when it is zero."""
    norm = float(np.linalg.norm(vector))
    if norm < _TOL:
        raise CADValidationError("direction/axis vector cannot be zero", code="invalid_direction")
    return vector / norm


def _rotation_align_z(direction: Point | np.ndarray[Any, Any]) -> list[list[float]]:
    """Return the 3x3 rotation mapping the local Z axis onto ``direction``."""
    axis = _unit(np.asarray(direction, dtype=float))
    z = np.array([0.0, 0.0, 1.0])
    v = np.cross(z, axis)
    c = float(np.dot(z, axis))
    if np.linalg.norm(v) < _TOL:
        if c > 0:
            return np.eye(3, dtype=float).tolist()  # type: ignore[no-any-return]
        return np.diag([-1.0, -1.0, 1.0]).astype(float).tolist()  # type: ignore[no-any-return]
    skew = np.array(
        [
            [0.0, -v[2], v[1]],
            [v[2], 0.0, -v[0]],
            [-v[1], v[0], 0.0],
        ],
        dtype=float,
    )
    matrix = (
        np.eye(3, dtype=float)
        + skew
        + skew @ skew * (1.0 / (1.0 + c))
    )
    return matrix.tolist()  # type: ignore[no-any-return]


def _rotation_about_axis(
    axis: Point | np.ndarray[Any, Any], degrees: float
) -> np.ndarray[Any, Any]:
    """Return the 3x3 rotation about ``axis`` by ``degrees`` (Rodrigues)."""
    unit = _unit(np.asarray(axis, dtype=float))
    radians = math.radians(degrees)
    cos_a = math.cos(radians)
    sin_a = math.sin(radians)
    k = np.asarray(unit, dtype=float)
    cross = np.array(
        [
            [0.0, -k[2], k[1]],
            [k[2], 0.0, -k[0]],
            [-k[1], k[0], 0.0],
        ],
        dtype=float,
    )
    return np.eye(3) * cos_a + (1.0 - cos_a) * np.outer(k, k) + sin_a * cross  # type: ignore[no-any-return, unused-ignore]


def _reflection_matrix(plane_point: Point, normal: Point) -> np.ndarray[Any, Any]:
    """Return the 4x4 reflection across the plane (``plane_point``, ``normal``)."""
    n = _unit(np.asarray(normal, dtype=float))
    point = np.asarray(plane_point, dtype=float)
    reflect_linear = np.eye(3) - 2.0 * np.outer(n, n)
    offset = 2.0 * np.dot(n, point)
    matrix = np.eye(4, dtype=float)
    matrix[:3, :3] = reflect_linear
    matrix[:3, 3] = offset * n
    return matrix


class FeatureManager:
    """Applies parametric features against a document's entity manager."""

    def __init__(self, entities: EntityManager, kernel: CADKernel | None = None) -> None:
        """Bind a feature manager to an entity manager and (optionally) a kernel."""
        self._entities = entities
        self._kernel = kernel or entities.kernel

    @property
    def kernel(self) -> CADKernel:
        """Return the underlying geometry kernel."""
        return self._kernel

    def _create_from_shape(
        self,
        shape: Shape,
        *,
        object_id: str | None,
        layer: str,
        properties: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> str:
        """Store a raw shape dict (kind+params) as a new entity."""
        return self._entities.create(
            shape["kind"],
            dict(shape["params"]),
            layer=layer,
            properties=properties,
            object_id=object_id,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Sweep
    # ------------------------------------------------------------------

    def sweep(
        self,
        profile_id: str,
        path: list[Point],
        *,
        object_id: str | None = None,
        layer: str = "0",
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Sweep a profile entity along a polyline path and store the result.

        Uses the OCCT kernel when available (full generality); otherwise
        falls back to an analytic straight sweep (circle -> cylinder,
        rectangle -> box). Curved analytic sweeps require the OCCT kernel.
        """
        if len(path) < 2:
            raise CADValidationError(
                "sweep requires a path of at least 2 points", code="invalid_path"
            )
        profile = self._entities.get(profile_id)
        path_points = [list(point) for point in path]
        kernel_sweep = getattr(self._kernel, "sweep", None)
        if kernel_sweep is not None:
            shape = kernel_sweep(profile.shape, path_points)
            return self._create_from_shape(
                shape, object_id=object_id, layer=layer,
                properties=properties, metadata=metadata,
            )
        shape = self._analytic_sweep(profile.shape, path_points)
        return self._create_from_shape(
            shape, object_id=object_id, layer=layer,
            properties=properties, metadata=metadata,
        )

    def _analytic_sweep(self, profile: Shape, path: list[list[float]]) -> Shape:
        points = [np.asarray(p, dtype=float) for p in path]
        direction = points[1] - points[0]
        length = float(np.linalg.norm(direction))
        if length <= _TOL:
            raise CADValidationError("sweep path cannot be zero-length", code="invalid_path")
        axis = _unit(direction)
        for point in points[2:]:
            if float(np.linalg.norm(np.cross(axis, point - points[0]))) > _TOL:
                raise CADNotImplementedError(
                    "analytic sweep only supports a straight path; use the OCCT kernel",
                    code="requires_occ",
                )
        kind = profile["kind"]
        params = profile["params"]
        if kind == "circle":
            return self._kernel.create_cylinder(
                points[0].tolist(), params["radius"], length, axis.tolist()
            )
        if kind == "rectangle":
            rotation = _rotation_align_z(axis)
            return self._kernel.create_box(
                points[0].tolist(),
                [params["width"], params["height"], length],
                rotation,
            )
        raise CADNotImplementedError(
            f"sweep of {kind} profiles requires the OCCT kernel", code="requires_occ"
        )

    # ------------------------------------------------------------------
    # Loft
    # ------------------------------------------------------------------

    def loft(
        self,
        profile_ids: list[str],
        sections: list[Point] | None = None,
        *,
        object_id: str | None = None,
        layer: str = "0",
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Loft between stacked profile entities and store the result.

        Uses the OCCT kernel when available (circle/rectangle profiles).
        The analytic fallback supports two concentric circles on the Z axis
        and represents the loft as a cone/cylinder.
        """
        if len(profile_ids) < 2:
            raise CADValidationError("loft requires at least 2 profiles", code="invalid_profiles")
        profiles = [self._entities.get(pid).shape for pid in profile_ids]
        section_points = [list(section) for section in sections] if sections else None
        kernel_loft = getattr(self._kernel, "loft", None)
        if kernel_loft is not None:
            shape = kernel_loft(profiles, section_points)
            return self._build_from_shape(shape, object_id, layer, properties, metadata)
        shape = self._analytic_loft(profiles)
        return self._build_from_shape(shape, object_id, layer, properties, metadata)

    def _build_from_shape(
        self,
        shape: Shape,
        object_id: str | None,
        layer: str,
        properties: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> str:
        return self._create_from_shape(
            shape, object_id=object_id, layer=layer,
            properties=properties, metadata=metadata,
        )

    def _analytic_loft(self, profiles: list[Shape]) -> Shape:
        if len(profiles) != 2:
            raise CADNotImplementedError(
                "analytic loft supports two profiles only; use the OCCT kernel",
                code="requires_occ",
            )
        first, last = profiles[0], profiles[1]
        for profile in profiles:
            if profile["kind"] != "circle":
                raise CADNotImplementedError(
                    "analytic loft supports concentric circles; use the OCCT kernel",
                    code="requires_occ",
                )
        p0 = np.asarray(first["params"]["center"], dtype=float)
        p1 = np.asarray(last["params"]["center"], dtype=float)
        if not np.isclose(p0[0], p1[0]) or not np.isclose(p0[1], p1[1]):
            raise CADNotImplementedError(
                "analytic loft requires coaxially-aligned circles; use the OCCT kernel",
                code="requires_occ",
            )
        height = float(p1[2] - p0[2])
        if height <= _TOL:
            raise CADValidationError(
                "loft profiles must be at distinct heights", code="invalid_profiles"
            )
        return self._kernel.create_cone(
            p0.tolist(),
            float(first["params"]["radius"]),
            float(last["params"]["radius"]),
            height,
        )

    # ------------------------------------------------------------------
    # Fillet / chamfer (exact only on the OCCT kernel)
    # ------------------------------------------------------------------

    def fillet(
        self,
        entity_id: str,
        radius: float,
        *,
        object_id: str | None = None,
        layer: str = "0",
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Blend entity edges with a fillet of ``radius``."""
        if radius <= 0:
            raise CADValidationError("fillet radius must be > 0", code="invalid_radius")
        record = self._entities.get(entity_id)
        kernel_fillet = getattr(self._kernel, "fillet", None)
        if kernel_fillet is None:
            raise CADNotImplementedError(
                "fillet requires the OCCT kernel (`pip install -e '.[occ]'`)",
                code="requires_occ",
            )
        shape = kernel_fillet(record.shape, radius)
        return self._create_from_shape(
            shape, object_id=object_id, layer=layer,
            properties=properties, metadata=metadata,
        )

    def chamfer(
        self,
        entity_id: str,
        size: float,
        *,
        object_id: str | None = None,
        layer: str = "0",
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Cut entity edges with a chamfer of ``size``."""
        if size <= 0:
            raise CADValidationError("chamfer size must be > 0", code="invalid_size")
        record = self._entities.get(entity_id)
        kernel_chamfer = getattr(self._kernel, "chamfer", None)
        if kernel_chamfer is None:
            raise CADNotImplementedError(
                "chamfer requires the OCCT kernel (`pip install -e '.[occ]'`)",
                code="requires_occ",
            )
        shape = kernel_chamfer(record.shape, size)
        return self._create_from_shape(
            shape, object_id=object_id, layer=layer,
            properties=properties, metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Patterns (pure rigid transforms, supported on every kernel)
    # ------------------------------------------------------------------

    def pattern_linear(
        self,
        entity_id: str,
        direction: Point,
        count: int,
        spacing: float,
        *,
        layer: str = "0",
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        """Copy ``entity_id`` in a linear grid along ``direction``.

        ``count`` instances are produced in total (including the original).
        Returns the ids in index order: ``[entity_id, copy_1, ...]``.
        """
        if count < 1:
            raise CADValidationError("pattern count must be >= 1", code="invalid_count")
        if spacing <= 0:
            raise CADValidationError("pattern spacing must be > 0", code="invalid_spacing")
        step = np.asarray(direction, dtype=float) * spacing
        ids: list[str] = [entity_id]
        for index in range(1, count):
            new_id = self._entities.copy(entity_id)
            self._transform_new(new_id, translation(*((step * index).tolist())))
            self._attach(new_id, layer, properties, metadata)
            ids.append(new_id)
        return ids

    def pattern_circular(
        self,
        entity_id: str,
        center: Point,
        axis: Point,
        count: int,
        angle: float = 360.0,
        *,
        layer: str = "0",
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[str]:
        """Copy ``entity_id`` in a circular pattern around ``axis`` through ``center``.

        ``count`` instances are produced evenly across the ``angle`` span.
        """
        if count < 2:
            raise CADValidationError("circular pattern count must be >= 2", code="invalid_count")
        if angle <= 0:
            raise CADValidationError("circular pattern angle must be > 0", code="invalid_angle")
        center_arr = np.asarray(center, dtype=float)
        axis_unit = _unit(np.asarray(axis, dtype=float))
        step = angle / float(count)
        ids: list[str] = [entity_id]
        for index in range(1, count):
            theta = step * index
            rot = _rotation_about_axis(axis_unit, theta)
            around = compose(
                translation(float(center_arr[0]), float(center_arr[1]), float(center_arr[2])),
                _to_matrix(rot),
                translation(-float(center_arr[0]), -float(center_arr[1]), -float(center_arr[2])),
            )
            new_id = self._entities.copy(entity_id)
            self._transform_new(new_id, around)
            self._attach(new_id, layer, properties, metadata)
            ids.append(new_id)
        return ids

    def pattern_mirror(
        self,
        entity_id: str,
        plane_point: Point,
        plane_normal: Point,
        *,
        new_id: str | None = None,
        layer: str = "0",
        properties: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Mirror ``entity_id`` across the plane (``plane_point``, ``plane_normal``)."""
        matrix = _reflection_matrix(plane_point, plane_normal)
        new_id = self._entities.copy(entity_id, new_id=new_id)
        self._transform_new(new_id, matrix)
        self._attach(new_id, layer, properties, metadata)
        return new_id

    def _transform_new(self, new_id: str, matrix: np.ndarray[Any, Any]) -> None:
        """Transform a freshly copied entity, preserving box rotation.

        The analytic box transform drops the linear part when the source
        box has no stored rotation, so rotated patterns special-case boxes
        by composing the rotation matrix directly.
        """
        from cad_mcp_server.core.transform import apply_point, rotation_part

        shape = self._entities.get(new_id).shape
        if shape["kind"] == "box":
            rot3 = np.asarray(rotation_part(matrix)[:3, :3], dtype=float)
            existing = shape["params"].get("rotation")
            composed = rot3 @ np.asarray(existing, dtype=float) if existing else rot3
            shape["params"]["rotation"] = np.asarray(composed, dtype=float).tolist()
            shape["params"]["origin"] = apply_point(matrix, shape["params"]["origin"])
            return
        self._entities.transform(new_id, matrix)

    def _attach(
        self,
        new_id: str,
        layer: str,
        properties: dict[str, Any] | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        """Update layer/properties/metadata on a freshly created copy."""
        record = self._entities.get(new_id)
        record.layer = layer
        if metadata or properties:
            record.properties.update(properties or {})
            record.metadata.update(metadata or {})


def _to_matrix(rotation_3x3: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    """Promote a 3x3 rotation to a 4x4 homogeneous matrix."""
    matrix = np.eye(4, dtype=float)
    matrix[:3, :3] = rotation_3x3
    return matrix
