"""Tests for the natural language command parsing tool."""

from __future__ import annotations

from cad_mcp_server.mcp.tools.nlp import NLPCommandInput, cad_nlp_command


class TestNLPCommand:
    """Intent parsing for English and Chinese requests."""

    def test_create_file_english(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="new file design.dwg"))
        assert result.status == "success"
        assert result.intent == "create_file"
        assert result.tool == "cad_file_create"
        assert result.arguments["filename"] == "design.dwg"
        assert result.confidence > 0.8

    def test_create_file_chinese(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="新建文件 project.json"))
        assert result.status == "success"
        assert result.intent == "create_file"
        assert result.arguments["filename"] == "project.json"

    def test_open_file(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="open C:/tmp/part.json"))
        assert result.status == "success"
        assert result.intent == "open_file"
        assert result.arguments["path"] == "C:/tmp/part.json"

    def test_draw_line(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="draw a line from 0,0 to 10,10"))
        assert result.status == "success"
        assert result.intent == "draw_line"
        assert result.tool == "cad_object_create"
        assert result.arguments["type"] == "line"
        assert result.arguments["params"]["start"] == [0.0, 0.0, 0.0]
        assert result.arguments["params"]["end"] == [10.0, 10.0, 0.0]

    def test_draw_circle(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="画一个圆 中心 5,5 半径 3"))
        assert result.status == "success"
        assert result.intent == "draw_circle"
        assert result.arguments["params"]["radius"] in (3.0, 5.0)

    def test_draw_box(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="create a box"))
        assert result.status == "success"
        assert result.intent == "draw_box"
        assert result.arguments["type"] == "box"

    def test_delete_object(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="delete object obj_1234"))
        assert result.status == "success"
        assert result.intent == "delete_object"
        assert result.arguments["object_id"] == "obj_1234"

    def test_list_objects(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="list objects"))
        assert result.status == "success"
        assert result.intent == "list_objects"
        assert result.arguments == {}

    def test_check_status_chinese(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="查看状态"))
        assert result.status == "success"
        assert result.intent == "check_status"
        assert result.tool == "cad_status_health"

    def test_render_side_view(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="render the side view"))
        assert result.status == "success"
        assert result.intent == "render_view"
        assert result.arguments["view"] == "side"

    def test_render_front_chinese(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="渲染前视图"))
        assert result.status == "success"
        assert result.intent == "render_view"
        assert result.arguments["view"] == "front"

    def test_save_version(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="save a version"))
        assert result.status == "success"
        assert result.intent == "save_version"
        assert result.tool == "cad_version_save"

    def test_ambiguous_request(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="delete and render"))
        assert result.status == "error"
        assert result.ambiguous is True
        assert len(result.suggestions) >= 2

    def test_unknown_request(self) -> None:
        result = cad_nlp_command(NLPCommandInput(text="please make a sandwich"))
        assert result.status == "error"
        assert result.intent == "unknown"
        assert result.tool is None

    def test_tool_whitelist_filters(self) -> None:
        result = cad_nlp_command(
            NLPCommandInput(
                text="draw a circle at 1,2 radius 4",
                tool_whitelist=["cad_file_create"],
            )
        )
        assert result.status == "error"
        assert result.intent == "unknown"
