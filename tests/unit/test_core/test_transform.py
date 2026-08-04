"""Tests for transformation matrices."""

from __future__ import annotations

import numpy as np
import pytest

from tianshangcad.core import transform as t


class TestMatrixBuilders:
    """Matrix construction tests."""

    def test_translation_applies(self) -> None:
        matrix = t.translation(10, 20, 30)
        assert t.apply_point(matrix, [0, 0, 0]) == [10.0, 20.0, 30.0]

    def test_identity_rotation(self) -> None:
        assert t.apply_point(t.rotation_z(0), [1, 0, 0]) == pytest.approx([1.0, 0.0, 0.0])

    def test_rotation_z_90(self) -> None:
        assert t.apply_point(t.rotation_z(90), [1, 0, 0]) == pytest.approx([0.0, 1.0, 0.0])

    def test_rotation_x_90(self) -> None:
        assert t.apply_point(t.rotation_x(90), [0, 1, 0]) == pytest.approx([0.0, 0.0, 1.0])

    def test_rotation_y_90(self) -> None:
        assert t.apply_point(t.rotation_y(90), [0, 0, 1]) == pytest.approx([1.0, 0.0, 0.0])

    def test_scale(self) -> None:
        matrix = t.scale(2, 3, 4)
        assert t.apply_point(matrix, [1, 1, 1]) == [2.0, 3.0, 4.0]

    def test_compose_order(self) -> None:
        combined = t.compose(t.translation(10, 0, 0), t.rotation_z(90))
        # rotation applied first, then translation
        assert t.apply_point(combined, [1, 0, 0]) == pytest.approx([10.0, 1.0, 0.0])

    def test_inverse(self) -> None:
        matrix = t.compose(t.translation(10, 0, 0), t.rotation_z(90))
        result = t.apply_point(t.compose(matrix, t.inverse(matrix)), [3, 4, 5])
        assert result == pytest.approx([3.0, 4.0, 5.0])


class TestHelpers:
    """Helper function tests."""

    def test_apply_points(self) -> None:
        matrix = t.translation(1, 2, 3)
        assert t.apply_points(matrix, [[0, 0, 0], [1, 1, 1]]) == [
            [1.0, 2.0, 3.0],
            [2.0, 3.0, 4.0],
        ]

    def test_uniform_scale(self) -> None:
        assert t.uniform_scale(t.scale(2, 2, 2)) == pytest.approx(2.0)

    def test_rotation_part(self) -> None:
        matrix = t.rotation_z(45)
        linear = t.rotation_part(matrix)
        assert linear.shape == (3, 3)

    def test_rotation_around_point(self) -> None:
        matrix = t.rotation_around_point_z(90, [10, 0, 0])
        result = t.apply_point(matrix, [20, 0, 0])
        assert result == pytest.approx([10.0, 10.0, 0.0])

    def test_scale_around_point(self) -> None:
        matrix = t.scale_around_point(2.0, [10, 0, 0])
        assert t.apply_point(matrix, [10, 0, 0]) == pytest.approx([10.0, 0.0, 0.0])
        assert t.apply_point(matrix, [20, 0, 0]) == pytest.approx([30.0, 0.0, 0.0])

    def test_matrices_are_4x4(self) -> None:
        matrices = (t.translation(), t.rotation_x(1), t.rotation_y(1), t.rotation_z(1), t.scale())
        for matrix in matrices:
            assert matrix.shape == (4, 4)
            assert isinstance(matrix, np.ndarray)
