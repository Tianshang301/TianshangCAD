"""Tests for the natural language command parsing tool."""

from __future__ import annotations

from tianshangcad.mcp.tools.nlp import (
    ChatInput,
    NLPCommandInput,
    cad_nlp_chat,
    cad_nlp_command,
)


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
        assert result.arguments["params"]["radius"] == 3.0

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


class TestNLPChat:
    """Multi-turn dialogue with anaphora resolution."""

    def test_chat_draw_then_move_with_pronoun(self, document) -> None:
        """Draw a circle, then 'move it' resolves to the created object."""
        first = cad_nlp_chat(ChatInput(session_id="s1", text="draw a circle at 5,5 radius 3"))
        assert first.status == "success"
        assert first.intent == "draw_circle"
        assert first.object_id
        assert first.turn == 1

        second = cad_nlp_chat(ChatInput(session_id="s1", text="move it to 10,10"))
        assert second.status == "success"
        assert second.intent == "move_object"
        assert second.object_id == first.object_id
        assert second.resolved is True
        assert second.turn == 2
        assert second.arguments["params"]["center"] == [10.0, 10.0, 0.0]

    def test_chat_chinese_anaphora(self, document) -> None:
        """Chinese dialogue: draw a circle, then move '它' (it)."""
        first = cad_nlp_chat(ChatInput(session_id="zh", text="画一个圆 中心 1,2"))
        assert first.status == "success"
        assert first.intent == "draw_circle"

        second = cad_nlp_chat(ChatInput(session_id="zh", text="把它移到 4,4"))
        assert second.intent == "move_object"
        assert second.resolved is True
        assert second.object_id == first.object_id
        assert second.arguments["params"]["center"] == [4.0, 4.0, 0.0]

    def test_move_explicit_reference(self, document) -> None:
        """'the circle I just drew' resolves to the previously created object."""
        first = cad_nlp_chat(ChatInput(session_id="s2", text="draw a circle at 0,0 radius 2"))
        second = cad_nlp_chat(
            ChatInput(session_id="s2", text="move the circle I just drew to 3,3")
        )
        assert second.intent == "move_object"
        assert second.object_id == first.object_id
        assert second.arguments["params"]["center"] == [3.0, 3.0, 0.0]

    def test_delete_anaphora(self, document) -> None:
        """Delete the object created in a previous turn."""
        first = cad_nlp_chat(ChatInput(session_id="s3", text="draw a box"))
        assert first.object_id

        second = cad_nlp_chat(ChatInput(session_id="s3", text="delete it"))
        assert second.intent == "delete_object"
        assert second.resolved is True
        assert second.object_id == first.object_id

    def test_anaphora_requires_prior_object(self) -> None:
        """Without a prior creation, anaphora cannot resolve."""
        result = cad_nlp_chat(ChatInput(session_id="empty", text="move it to 5,5"))
        assert result.intent == "move_object"
        assert result.resolved is False
        assert result.object_id is None

    def test_sessions_are_isolated(self, document) -> None:
        """Dialogue state does not leak across session ids."""
        cad_nlp_chat(ChatInput(session_id="a", text="draw a circle at 1,1 radius 1"))
        result = cad_nlp_chat(ChatInput(session_id="b", text="move it to 2,2"))
        assert result.resolved is False
        assert result.object_id is None

    def test_move_line_translates_endpoint(self, document) -> None:
        """Moving a line translates both endpoints by the delta."""
        cad_nlp_chat(
            ChatInput(session_id="s4", text="draw a line from 0,0 to 10,0")
        )
        second = cad_nlp_chat(ChatInput(session_id="s4", text="move it to 5,5"))
        updated_params = second.arguments["params"]
        assert updated_params["start"] == [5.0, 5.0, 0.0]
        assert updated_params["end"] == [15.0, 5.0, 0.0]
