"""MCP variable tool tests."""

from __future__ import annotations

from tianshangcad.mcp.tools.variables import (
    VariableInput,
    VariableListInput,
    VariableListParams,
    VariableSetInput,
    VariableSetParams,
    cad_variable,
    cad_variable_list,
    cad_variable_set,
)


class TestVariableTools:
    """`cad_variable_*` tool tests."""

    def _setup_file(self) -> None:
        from tianshangcad.mcp.tools.crud import FileCreateInput, cad_file_create

        cad_file_create(FileCreateInput(filename="var.json"))

    def test_variable_set_success(self) -> None:
        self._setup_file()
        result = cad_variable_set(VariableSetInput(name="width", value=50, unit="mm"))
        assert result.status == "success"
        assert result.value == 50
        assert result.unit == "mm"

    def test_variable_set_expression(self) -> None:
        self._setup_file()
        cad_variable_set(VariableSetInput(name="w", value=50))
        result = cad_variable_set(VariableSetInput(name="depth", expr="w * 2"))
        assert result.status == "success"
        assert result.value == 100

    def test_variable_set_error(self) -> None:
        self._setup_file()
        result = cad_variable_set(VariableSetInput(name="a", expr="missing + 1"))
        assert result.status == "error"
        assert "Undefined variable" in result.message

    def test_variable_list(self) -> None:
        self._setup_file()
        cad_variable_set(VariableSetInput(name="width", value=50))
        cad_variable_set(VariableSetInput(name="depth", expr="width * 2"))
        result = cad_variable_list(VariableListInput())
        assert result.status == "success"
        assert result.count == 2
        assert {v["name"] for v in result.variables} == {"width", "depth"}

    def test_variable_list_empty(self) -> None:
        self._setup_file()
        result = cad_variable_list(VariableListInput())
        assert result.status == "success"
        assert result.count == 0

    def test_variable_set_no_document(self) -> None:
        from tianshangcad.mcp.tools.status import SessionManager

        SessionManager().reset()
        result = cad_variable_set(VariableSetInput(name="width", value=1))
        assert result.status == "error"
        assert "No active document" in result.message

    def test_variable_list_persists_roundtrip(self) -> None:
        from tianshangcad.core.session import SessionManager

        self._setup_file()
        cad_variable_set(VariableSetInput(name="width", value=50, unit="mm"))
        doc = SessionManager().current_session.current_file_id
        from tianshangcad.core.document import DocumentManager

        data = DocumentManager()._require(doc).to_dict()
        assert any(v["name"] == "width" for v in data["variables"])


class TestVariableAggregate:
    """Aggregate cad_variable tool (discriminated action)."""

    def _setup_file(self) -> None:
        from tianshangcad.mcp.tools.crud import FileCreateInput, cad_file_create

        cad_file_create(FileCreateInput(filename="var.json"))

    def test_action_set_success_and_expr(self) -> None:
        self._setup_file()
        ok = cad_variable(
            VariableInput(variable=VariableSetParams(name="width", value=50, unit="mm"))
        )
        assert ok.status == "success"
        assert ok.action == "set"
        assert ok.value == 50
        assert ok.unit == "mm"
        cad_variable(VariableInput(variable=VariableSetParams(name="w", value=50)))
        depth = cad_variable(
            VariableInput(variable=VariableSetParams(name="depth", expr="w * 2"))
        )
        assert depth.status == "success"
        assert depth.value == 100

    def test_action_set_error(self) -> None:
        self._setup_file()
        result = cad_variable(
            VariableInput(variable=VariableSetParams(name="a", expr="missing + 1"))
        )
        assert result.status == "error"
        assert "Undefined variable" in result.message

    def test_action_set_no_document(self) -> None:
        from tianshangcad.mcp.tools.status import SessionManager

        SessionManager().reset()
        result = cad_variable(
            VariableInput(variable=VariableSetParams(name="width", value=1))
        )
        assert result.status == "error"
        assert "No active document" in result.message

    def test_action_list_and_empty(self) -> None:
        self._setup_file()
        empty = cad_variable(VariableInput(variable=VariableListParams()))
        assert empty.status == "success"
        assert empty.count == 0
        cad_variable(VariableInput(variable=VariableSetParams(name="width", value=50)))
        cad_variable(VariableInput(variable=VariableSetParams(name="depth", expr="width * 2")))
        listed = cad_variable(VariableInput(variable=VariableListParams()))
        assert listed.count == 2
        assert {v["name"] for v in listed.variables} == {"width", "depth"}
