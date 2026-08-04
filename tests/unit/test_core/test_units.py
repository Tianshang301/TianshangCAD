"""Tests for unit conversion helpers."""

from __future__ import annotations

import pytest

from tianshangcad.utils.errors import CADValidationError
from tianshangcad.utils.units import (
    from_mm,
    scale_factor,
    to_mm,
    validate_unit,
)


class TestUnits:
    """Unit conversion tests."""

    def test_to_mm(self) -> None:
        assert to_mm(1, "mm") == 1
        assert to_mm(1, "cm") == 10
        assert to_mm(1, "m") == 1000
        assert to_mm(1, "in") == pytest.approx(25.4)
        assert to_mm(1, "ft") == pytest.approx(304.8)

    def test_from_mm_roundtrip(self) -> None:
        for unit in ("mm", "cm", "m", "in", "ft"):
            assert from_mm(to_mm(123.4, unit), unit) == pytest.approx(123.4)

    def test_scale_factor(self) -> None:
        assert scale_factor("m", "mm") == 1000
        assert scale_factor("cm", "m") == 0.01

    def test_validate_unit_case_insensitive(self) -> None:
        assert validate_unit("MM") == "mm"
        assert validate_unit(" In ") == "in"

    def test_invalid_unit(self) -> None:
        with pytest.raises(CADValidationError):
            validate_unit("furlong")
