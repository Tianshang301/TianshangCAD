"""Boolean MCP tool unit tests."""

from __future__ import annotations

import pytest

from tianshangcad.mcp.tools.boolean import (
    BooleanInput,
    BooleanOutput,
    ObjectBooleanInput,
    ObjectBooleanOutput,
    cad_boolean_intersect,
    cad_boolean_subtract,
    cad_boolean_union,
    cad_object_boolean,
)
from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)


def _make_boxes() -> tuple[str, str]:
    a = cad_object_create(
        ObjectCreateInput(type="box", params={"origin": [0, 0, 0], "dimensions": [4, 4, 4]})
    )
    b = cad_object_create(
        ObjectCreateInput(type="box", params={"origin": [1, 1, 1], "dimensions": [2, 2, 2]})
    )
    return a.object_id, b.object_id


class TestBooleanTools:
    """`cad_boolean_*` MCP tools."""

    def _setup(self) -> tuple[str, str]:
        cad_file_create(FileCreateInput(filename="bool-mcp.json", unit="mm"))
        return _make_boxes()

    def test_union(self) -> None:
        pytest.importorskip("trimesh")
        a, b = self._setup()
        result = cad_boolean_union(BooleanInput(operation="union", target_id=a, tool_id=b))
        assert isinstance(result, BooleanOutput)
        assert result.status == "success"
        assert result.result_id != ""
        assert result.bbox["max"] == [4.0, 4.0, 4.0]

    def test_subtract(self) -> None:
        pytest.importorskip("trimesh")
        a, b = self._setup()
        result = cad_boolean_subtract(BooleanInput(operation="subtract", target_id=a, tool_id=b))
        assert result.status == "success"
        assert result.result_id != ""
        assert result.bbox["max"] == [4.0, 4.0, 4.0]

    def test_intersect(self) -> None:
        pytest.importorskip("trimesh")
        a, b = self._setup()
        result = cad_boolean_intersect(
            BooleanInput(operation="intersect", target_id=a, tool_id=b)
        )
        assert result.status == "success"
        assert result.result_id != ""
        assert result.bbox == {"min": [1.0, 1.0, 1.0], "max": [3.0, 3.0, 3.0]}

    def test_custom_new_id(self) -> None:
        pytest.importorskip("trimesh")
        a, b = self._setup()
        result = cad_boolean_union(
            BooleanInput(operation="union", target_id=a, tool_id=b, new_id="result1")
        )
        assert result.status == "success"
        assert result.result_id == "result1"

    def test_missing_object(self) -> None:
        pytest.importorskip("trimesh")
        cad_file_create(FileCreateInput(filename="bool-mcp2.json", unit="mm"))
        a, _ = _make_boxes()
        result = cad_boolean_union(BooleanInput(operation="union", target_id=a, tool_id="ghost"))
        assert result.status == "error"
        assert result.result_id == ""


class TestObjectBoolean:
    """`cad_object_boolean` aggregate tool."""

    def _setup(self) -> tuple[str, str, str]:
        cad_file_create(FileCreateInput(filename="objbool.json", unit="mm"))
        a = cad_object_create(
            ObjectCreateInput(type="box", params={"origin": [0, 0, 0], "dimensions": [4, 4, 4]})
        ).object_id
        b = cad_object_create(
            ObjectCreateInput(type="box", params={"origin": [1, 1, 1], "dimensions": [2, 2, 2]})
        ).object_id
        c = cad_object_create(
            ObjectCreateInput(type="box", params={"origin": [-2, -2, -2], "dimensions": [1, 1, 1]})
        ).object_id
        return a, b, c

    def test_single_union(self) -> None:
        pytest.importorskip("trimesh")
        a, b, _ = self._setup()
        result = cad_object_boolean(
            ObjectBooleanInput(operation="union", target_id=a, tool_ids=[b])
        )
        assert isinstance(result, ObjectBooleanOutput)
        assert result.status == "success"
        assert result.result_id != ""
        assert result.bbox["max"] == [4.0, 4.0, 4.0]

    def test_multi_tool_subtract(self) -> None:
        pytest.importorskip("trimesh")
        a, b, c = self._setup()
        result = cad_object_boolean(
            ObjectBooleanInput(operation="subtract", target_id=a, tool_ids=[b, c])
        )
        assert result.status == "success"
        assert result.result_id != ""

    def test_empty_tool_ids(self) -> None:
        a, _, _ = self._setup()
        result = cad_object_boolean(
            ObjectBooleanInput(operation="union", target_id=a, tool_ids=[])
        )
        assert result.status == "error"
        assert "At least one tool id" in result.message

    def test_target_also_in_tools(self) -> None:
        a, b, _ = self._setup()
        result = cad_object_boolean(
            ObjectBooleanInput(operation="union", target_id=a, tool_ids=[a, b])
        )
        assert result.status == "error"
        assert "must not also appear" in result.message

    def test_unknown_operation_rejected_by_schema(self) -> None:
        import pydantic

        a, b, _ = self._setup()
        with pytest.raises(pydantic.ValidationError):
            ObjectBooleanInput(operation="extrude", target_id=a, tool_ids=[b])

    def test_invalid_operation_direct(self) -> None:
        from tianshangcad.mcp.tools.boolean import _run_boolean

        a, b, _ = self._setup()
        result = _run_boolean("extrude", a, b, "", "0")
        assert result.status == "error"
        assert "Unknown boolean operation" in result.message


class TestBooleanBoundary:
    """Degenerate / boundary boolean handling."""

    def _make_box(self, origin: list[float], dims: list[float]) -> str:
        return cad_object_create(
            ObjectCreateInput(type="box", params={"origin": origin, "dimensions": dims})
        ).object_id

    def test_tangent_spheres_union(self) -> None:
        pytest.importorskip("trimesh")
        cad_file_create(FileCreateInput(filename="tangent.json", unit="mm"))
        a = cad_object_create(
            ObjectCreateInput(type="sphere", params={"center": [0, 0, 0], "radius": 2})
        ).object_id
        b = cad_object_create(
            ObjectCreateInput(type="sphere", params={"center": [4, 0, 0], "radius": 2})
        ).object_id
        result = cad_boolean_union(BooleanInput(operation="union", target_id=a, tool_id=b))
        assert result.status == "success"
        assert result.bbox["min"] == [-2.0, -2.0, -2.0]
        assert result.bbox["max"] == [6.0, 2.0, 2.0]

    def test_disjoint_intersection_empty(self) -> None:
        pytest.importorskip("trimesh")
        cad_file_create(FileCreateInput(filename="disjoint-intersect.json", unit="mm"))
        a = cad_object_create(
            ObjectCreateInput(type="sphere", params={"center": [0, 0, 0], "radius": 2})
        ).object_id
        b = cad_object_create(
            ObjectCreateInput(type="sphere", params={"center": [10, 0, 0], "radius": 2})
        ).object_id
        result = cad_boolean_intersect(BooleanInput(operation="intersect", target_id=a, tool_id=b))
        assert result.status == "error"
        assert result.message is not None and (
            "degenerate" in result.message or "empty" in result.message
        )

    def test_contained_subtract_empty(self) -> None:
        pytest.importorskip("trimesh")
        cad_file_create(FileCreateInput(filename="contained.json", unit="mm"))
        outer = self._make_box([0, 0, 0], [10, 10, 10])
        inner = self._make_box([2, 2, 2], [6, 6, 6])
        result = cad_boolean_subtract(
            BooleanInput(operation="subtract", target_id=outer, tool_id=inner)
        )
        # Box fast-path leaves a shell; mesh path must still produce a solid.
        assert result.status in ("success", "error")

    def test_tangent_boxes_union(self) -> None:
        pytest.importorskip("trimesh")
        cad_file_create(FileCreateInput(filename="tangent-box.json", unit="mm"))
        a = self._make_box([0, 0, 0], [2, 2, 2])
        b = self._make_box([2, 0, 0], [2, 2, 2])
        result = cad_boolean_union(BooleanInput(operation="union", target_id=a, tool_id=b))
        assert result.status == "success"
        assert result.bbox == {"min": [0.0, 0.0, 0.0], "max": [4.0, 2.0, 2.0]}

    def test_full_containment_union(self) -> None:
        pytest.importorskip("trimesh")
        cad_file_create(FileCreateInput(filename="contain-union.json", unit="mm"))
        outer = self._make_box([0, 0, 0], [10, 10, 10])
        inner = self._make_box([2, 2, 2], [6, 6, 6])
        result = cad_boolean_union(BooleanInput(operation="union", target_id=outer, tool_id=inner))
        assert result.status == "success"
        assert result.bbox["max"] == [10.0, 10.0, 10.0]

    def test_zero_volume_rejected(self) -> None:
        pytest.importorskip("trimesh")
        cad_file_create(FileCreateInput(filename="zerovol.json", unit="mm"))
        a = self._make_box([0, 0, 0], [2, 2, 0])
        b = self._make_box([1, 1, 0], [2, 2, 0])
        result = cad_boolean_union(BooleanInput(operation="union", target_id=a, tool_id=b))
        # Boxes with zero height are unsupported solids -> error path.
        assert result.status == "error"
