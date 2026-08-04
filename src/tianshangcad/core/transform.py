"""Transformation matrices (4x4 homogeneous) built on numpy."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

Matrix4 = np.ndarray[Any, Any]


def translation(dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> Matrix4:
    """Return a 4x4 translation matrix."""
    matrix = np.eye(4)
    matrix[0, 3] = dx
    matrix[1, 3] = dy
    matrix[2, 3] = dz
    return matrix


def rotation_x(degrees: float) -> Matrix4:
    """Return a 4x4 rotation matrix about the X axis (degrees)."""
    radians = math.radians(degrees)
    c, s = math.cos(radians), math.sin(radians)
    matrix = np.eye(4)
    matrix[1, 1] = c
    matrix[1, 2] = -s
    matrix[2, 1] = s
    matrix[2, 2] = c
    return matrix


def rotation_y(degrees: float) -> Matrix4:
    """Return a 4x4 rotation matrix about the Y axis (degrees)."""
    radians = math.radians(degrees)
    c, s = math.cos(radians), math.sin(radians)
    matrix = np.eye(4)
    matrix[0, 0] = c
    matrix[0, 2] = s
    matrix[2, 0] = -s
    matrix[2, 2] = c
    return matrix


def rotation_z(degrees: float) -> Matrix4:
    """Return a 4x4 rotation matrix about the Z axis (degrees)."""
    radians = math.radians(degrees)
    c, s = math.cos(radians), math.sin(radians)
    matrix = np.eye(4)
    matrix[0, 0] = c
    matrix[0, 1] = -s
    matrix[1, 0] = s
    matrix[1, 1] = c
    return matrix


def scale(sx: float = 1.0, sy: float = 1.0, sz: float = 1.0) -> Matrix4:
    """Return a 4x4 scale matrix."""
    return np.diag([sx, sy, sz, 1.0])


def compose(*matrices: Matrix4) -> Matrix4:
    """Multiply matrices left-to-right: ``compose(A, B)`` = A @ B.

    The leftmost matrix is applied last, so ``compose(T, R)`` rotates
    first and then translates (``T @ R @ v``).
    """
    result = np.eye(4)
    for matrix in matrices:
        result = result @ matrix
    return result


def inverse(matrix: Matrix4) -> Matrix4:
    """Return the inverse of ``matrix``."""
    return np.linalg.inv(matrix)


def apply_point(matrix: Matrix4, point: Sequence[float]) -> list[float]:
    """Apply a 4x4 matrix to a point (x, y, z)."""
    x, y, z = (float(value) for value in point)
    vector = np.array([x, y, z, 1.0])
    transformed = matrix @ vector
    return [float(transformed[0]), float(transformed[1]), float(transformed[2])]


def apply_points(matrix: Matrix4, points: Sequence[Sequence[float]]) -> list[list[float]]:
    """Apply a 4x4 matrix to a sequence of points."""
    return [apply_point(matrix, point) for point in points]


def rotation_part(matrix: Matrix4) -> Matrix4:
    """Return the 3x3 rotation/scale part of ``matrix``."""
    return matrix[:3, :3]


def uniform_scale(matrix: Matrix4) -> float:
    """Estimate the uniform scale factor of ``matrix``.

    Uses the average singular value of the 3x3 linear part.
    """
    linear = rotation_part(matrix)
    singular_values = np.linalg.svd(linear, compute_uv=False)
    return float(np.mean(singular_values))


def rotation_around_point_z(degrees: float, center: Sequence[float]) -> Matrix4:
    """Return a rotation about the Z axis around an arbitrary center point."""
    cx, cy, _ = (float(value) for value in center)
    return compose(
        translation(cx, cy, 0.0),
        rotation_z(degrees),
        translation(-cx, -cy, 0.0),
    )


def scale_around_point(factor: float, center: Sequence[float]) -> Matrix4:
    """Return a uniform scale around an arbitrary center point."""
    cx, cy, cz = (float(value) for value in center)
    return compose(
        translation(cx, cy, cz),
        scale(factor, factor, factor),
        translation(-cx, -cy, -cz),
    )
