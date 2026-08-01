"""CLI render command tests."""

from __future__ import annotations

from typer.testing import CliRunner

from cad_mcp_server.cli.main import app
from cad_mcp_server.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)

runner = CliRunner()


def _seed() -> None:
    cad_file_create(FileCreateInput(filename="draw.json"))
    cad_object_create(
        ObjectCreateInput(
            type="box",
            params={"origin": [0, 0, 0], "dimensions": [10, 5, 2]},
            layer="0",
        )
    )


class TestRenderCommands:
    """`cad-cli render` command tests."""

    def test_render_view(self, tmp_path) -> None:
        _seed()
        target = tmp_path / "preview.png"
        result = runner.invoke(
            app, ["render", "view", "--view", "top", "--output", str(target)]
        )
        assert result.exit_code == 0
        assert target.exists()

    def test_render_view_invalid(self) -> None:
        _seed()
        result = runner.invoke(app, ["render", "view", "--view", "isometric"])
        assert result.exit_code != 0

    def test_render_3d(self, tmp_path) -> None:
        _seed()
        target = tmp_path / "preview3d.png"
        result = runner.invoke(app, ["render", "3d", "--output", str(target)])
        assert result.exit_code == 0
        assert target.exists()

    def test_render_webgl(self, tmp_path) -> None:
        _seed()
        data = tmp_path / "data.json"
        viewer = tmp_path / "viewer.html"
        result = runner.invoke(
            app,
            [
                "render",
                "webgl",
                "--output",
                str(data),
                "--viewer",
                str(viewer),
            ],
        )
        assert result.exit_code == 0
        assert data.exists()
        assert viewer.exists()

    def test_render_status(self) -> None:
        result = runner.invoke(app, ["render", "status"])
        assert result.exit_code == 0
        assert "matplotlib" in result.stdout

    def test_render_without_document_fails(self) -> None:
        result = runner.invoke(app, ["render", "view"])
        assert result.exit_code != 0
