"""Parametric variable manager tests."""

from __future__ import annotations

import pytest

from tianshangcad.core.variables import VariableManager
from tianshangcad.utils.errors import VariableError


class TestVariableSet:
    """Variable set / read behaviour."""

    def test_set_plain_value(self) -> None:
        mgr = VariableManager()
        record = mgr.set("width", value=50, unit="mm")
        assert record.value == 50
        assert record.unit == "mm"
        assert mgr.resolve("width") == 50

    def test_set_expression(self) -> None:
        mgr = VariableManager()
        mgr.set("w", value=50)
        record = mgr.set("depth", expr="w * 2")
        assert record.value == 100
        assert mgr.resolve("depth") == 100

    def test_set_expression_requires_value_or_expr(self) -> None:
        mgr = VariableManager()
        with pytest.raises(VariableError, match="requires a value or an expression"):
            mgr.set("x")

    def test_invalid_name(self) -> None:
        mgr = VariableManager()
        with pytest.raises(VariableError, match="Invalid variable name"):
            mgr.set("1bad", value=1)

    def test_update_overwrites(self) -> None:
        mgr = VariableManager()
        mgr.set("width", value=50)
        mgr.set("width", value=80)
        assert mgr.resolve("width") == 80

    def test_get_missing(self) -> None:
        mgr = VariableManager()
        with pytest.raises(VariableError, match="Variable not found"):
            mgr.get("missing")

    def test_delete(self) -> None:
        mgr = VariableManager()
        mgr.set("width", value=50)
        mgr.delete("width")
        assert mgr.list() == []

    def test_delete_missing(self) -> None:
        mgr = VariableManager()
        with pytest.raises(VariableError, match="Variable not found"):
            mgr.delete("nope")


class TestExpressionEvaluation:
    """Expression evaluation edge cases."""

    def test_expression_undefined_variable(self) -> None:
        mgr = VariableManager()
        with pytest.raises(VariableError, match="Undefined variable"):
            mgr.set("a", expr="b + 1")

    def test_expression_self_reference(self) -> None:
        mgr = VariableManager()
        with pytest.raises(VariableError, match="Circular variable reference"):
            mgr.set("a", expr="a + 1")

    def test_expression_circular_pair(self) -> None:
        mgr = VariableManager()
        mgr.set("b", value=1)
        mgr.set("a", expr="b + 1")
        with pytest.raises(VariableError, match="Circular variable reference"):
            mgr.set("b", expr="a + 1")

    def test_expression_unsupported_element(self) -> None:
        mgr = VariableManager()
        mgr.set("w", value=10)
        with pytest.raises(VariableError, match="Unsupported expression element"):
            mgr.set("a", expr="__import__('os').system('echo hi')")

    def test_expression_invalid_syntax(self) -> None:
        mgr = VariableManager()
        with pytest.raises(VariableError, match="Invalid expression"):
            mgr.set("a", expr="1 +")

    def test_expression_division_by_zero(self) -> None:
        mgr = VariableManager()
        mgr.set("z", value=0)
        with pytest.raises(ZeroDivisionError):
            mgr.set("a", expr="1 / z")

    def test_expression_updates_follow_dependency(self) -> None:
        mgr = VariableManager()
        mgr.set("w", value=50)
        mgr.set("depth", expr="w * 2")
        mgr.set("w", value=75)
        assert mgr.resolve("depth") == 150


class TestInterpolation:
    """Brace interpolation behaviour."""

    def test_interpolate_basic(self) -> None:
        mgr = VariableManager()
        mgr.set("width", value=50)
        assert mgr.interpolate("0,0 {width},0") == "0,0 50,0"

    def test_interpolate_float_formats_integral(self) -> None:
        mgr = VariableManager()
        mgr.set("r", value=25.0)
        assert mgr.interpolate("{r}") == "25"

    def test_interpolate_non_integral(self) -> None:
        mgr = VariableManager()
        mgr.set("r", value=2.5)
        assert mgr.interpolate("{r}") == "2.5"

    def test_interpolate_undefined_raises(self) -> None:
        mgr = VariableManager()
        with pytest.raises(VariableError, match="Variable not found"):
            mgr.interpolate("{missing}")

    def test_interpolate_no_tokens_passthrough(self) -> None:
        mgr = VariableManager()
        assert mgr.interpolate("10,20") == "10,20"


class TestSerialization:
    """Snapshot / restore roundtrip."""

    def test_snapshot_restore_roundtrip(self) -> None:
        mgr = VariableManager()
        mgr.set("width", value=50, unit="mm")
        mgr.set("depth", expr="width * 2")
        snap = mgr.snapshot()
        restored = VariableManager()
        restored.restore(snap)
        assert restored.resolve("width") == 50
        assert restored.resolve("depth") == 100
        assert restored.list()[0].unit == "mm"

    def test_record_to_from_dict(self) -> None:
        from tianshangcad.core.variables import VariableRecord

        record = VariableRecord("h", value=10.0, unit="cm", expr=None)
        data = record.to_dict()
        rebuilt = VariableRecord.from_dict(data)
        assert rebuilt.name == "h"
        assert rebuilt.value == 10.0
        assert rebuilt.unit == "cm"
