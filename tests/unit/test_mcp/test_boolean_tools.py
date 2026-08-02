"""Boolean MCP tool unit tests."""

from __future__ import annotations

import pytest

from cad_mcp_server.mcp.tools.boolean import (
    BooleanInput,
    BooleanOutput,
    cad_boolean_intersect,
    cad_boolean_subtract,
    cad_boolean_union,
)
from cad_mcp_server.mcp.tools.crud import (
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
