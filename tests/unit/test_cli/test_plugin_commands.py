"""CLI plugin management command tests."""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

from tianshangcad.cli.main import app
from tianshangcad.core.plugins import CADPlugin, PluginManager, PluginManifest, PluginPermission

runner = CliRunner()


class _CLIPlugin(CADPlugin):
    manifest = PluginManifest(
        name="cli_test",
        version="1.0.0",
        description="CLI test plugin",
        permissions=[PluginPermission.TOOLS],
    )

    def register_tools(self, registry: dict[str, Any]) -> None:
        registry["cli_test_ping"] = lambda: {"ok": True}


@pytest.fixture(autouse=True)
def _reset_manager() -> Any:
    PluginManager.reset()
    yield
    PluginManager.reset()


def _run(*args: str):
    return runner.invoke(app, [*args])


def test_list_discovers_plugins() -> None:
    result = _run("plugin", "list")
    assert result.exit_code == 0, result.output
    assert "gltf" in result.output
    assert "cam" in result.output


def test_install_and_list() -> None:
    installed = _run("plugin", "install", f"{__name__}:_CLIPlugin")
    assert installed.exit_code == 0, installed.output
    assert "Installed plugin cli_test" in installed.output

    listed = _run("plugin", "list")
    assert listed.exit_code == 0, listed.output
    assert "cli_test" in listed.output
    assert "[enabled]" in listed.output


def test_manifest() -> None:
    _run("plugin", "install", f"{__name__}:_CLIPlugin")
    result = _run("plugin", "manifest", "cli_test")
    assert result.exit_code == 0, result.output
    assert '"version": "1.0.0"' in result.output


def test_disable_enable_and_uninstall() -> None:
    _run("plugin", "install", f"{__name__}:_CLIPlugin")

    disabled = _run("plugin", "disable", "cli_test")
    assert disabled.exit_code == 0, disabled.output

    enabled = _run("plugin", "enable", "cli_test")
    assert enabled.exit_code == 0, enabled.output

    uninstalled = _run("plugin", "uninstall", "cli_test")
    assert uninstalled.exit_code == 0, uninstalled.output
    assert PluginManager().get_manifest("cli_test") is None


def test_invalid_reference_reports_error() -> None:
    result = _run("plugin", "install", "no_such_module:NoAttr")
    assert result.exit_code == 1
    assert "Error:" in result.output
