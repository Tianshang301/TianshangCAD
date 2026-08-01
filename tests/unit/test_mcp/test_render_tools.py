"""Tests for the render MCP tool."""

from __future__ import annotations

from cad_mcp_server.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from cad_mcp_server.mcp.tools.render import (
    RenderViewInput,
    cad_render_view,
)


def _seed() -> None:
    cad_file_create(FileCreateInput(filename="draw.json"))
    cad_object_create(
        ObjectCreateInput(
            type="box",
            params={"origin": [0, 0, 0], "dimensions": [10, 5, 2]},
            layer="0",
        )
    )


class TestRenderTool:
    """cad_render_view tool behaviour."""

    def test_render_success(self) -> None:
        _seed()
        result = cad_render_view(RenderViewInput(view="top", dpi=96))
        assert result.status == "success"
        assert result.path
        assert result.size_bytes > 1000
        assert result.data_uri.startswith("data:image/png;base64,")

    def test_render_writes_output(self, tmp_path) -> None:
        _seed()
        target = tmp_path / "preview.png"
        result = cad_render_view(RenderViewInput(view="front", output=str(target)))
        assert result.status == "success"
        assert result.path == str(target)
        assert target.exists()

    def test_invalid_view_error(self) -> None:
        _seed()
        result = cad_render_view(RenderViewInput(view="isometric"))
        assert result.status == "error"
        assert result.path == ""

    def test_no_document_error(self) -> None:
        result = cad_render_view(RenderViewInput(view="top"))
        assert result.status == "error"
        assert "No active document" in result.message
