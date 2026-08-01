"""Unit tests for batch command templates."""

from __future__ import annotations

import pytest

from cad_mcp_server.core.batch_templates import list_templates, render_template
from cad_mcp_server.utils.errors import SchedulerError


class TestTemplates:
    """Jinja2 batch template rendering."""

    def test_list_templates(self) -> None:
        names = list_templates()
        assert "cleanup" in names
        assert "export_all" in names
        assert "backup_json" in names

    def test_render_cleanup(self) -> None:
        commands = render_template("cleanup")
        assert isinstance(commands, list)
        assert commands[0]["tool"] == "cad_logs_clear"
        assert commands[1]["tool"] == "cad_status_health"

    def test_render_export_all(self) -> None:
        commands = render_template("export_all")
        tools = [command["tool"] for command in commands]
        assert "cad_json_export_scene" in tools
        assert "cad_json_export_geometry" in tools
        assert commands[0]["tool"] == "cad_file_save"

    def test_render_backup_json(self) -> None:
        commands = render_template("backup_json")
        assert commands[-1]["tool"] == "cad_json_export_scene"

    def test_render_with_j2_extension(self) -> None:
        commands = render_template("cleanup.j2")
        assert commands[0]["tool"] == "cad_logs_clear"

    def test_render_unknown_template_rejected(self) -> None:
        with pytest.raises(SchedulerError):
            render_template("does_not_exist")

    def test_render_variables_are_ignored_when_unused(self) -> None:
        commands = render_template("cleanup", {"unused": True})
        assert len(commands) == 2
