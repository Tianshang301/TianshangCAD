"""Unit tests for the cad_plugin aggregate tool."""

from __future__ import annotations

from typing import Any

import pytest

from tianshangcad.core.plugins import CADPlugin, PluginManager, PluginManifest, PluginPermission
from tianshangcad.mcp.tools.plugin import (
    PluginInput,
    PluginInstallParams,
    PluginListParams,
    PluginManifestParams,
    PluginUninstallParams,
    cad_plugin,
)


class _TestPlugin(CADPlugin):
    manifest = PluginManifest(
        name="mcp_test",
        version="1.0.0",
        description="MCP test plugin",
        permissions=[PluginPermission.TOOLS],
    )

    def register_tools(self, registry: dict[str, Any]) -> None:
        registry["mcp_test_ping"] = lambda: {"ok": True}


@pytest.fixture(autouse=True)
def _reset_manager() -> Any:
    PluginManager.reset()
    yield
    PluginManager.reset()


def _install() -> str:
    return cad_plugin(
        PluginInput(
            plugin=PluginInstallParams(entry_point=f"{__name__}:_TestPlugin")
        )
    ).name


class TestInstall:
    def test_install_success(self) -> None:
        result = cad_plugin(
            PluginInput(plugin=PluginInstallParams(entry_point=f"{__name__}:_TestPlugin"))
        )
        assert result.status == "success"
        assert result.name == "mcp_test"

    def test_install_invalid_reference_returns_error(self) -> None:
        result = cad_plugin(
            PluginInput(plugin=PluginInstallParams(entry_point="no_such_module:NoAttr"))
        )
        assert result.status == "error"
        assert result.message


class TestLifecycleActions:
    def test_uninstall(self) -> None:
        _install()
        result = cad_plugin(
            PluginInput(plugin=PluginUninstallParams(name="mcp_test"))
        )
        assert result.status == "success"
        assert PluginManager().get_manifest("mcp_test") is None

    def test_uninstall_unknown_returns_error(self) -> None:
        result = cad_plugin(
            PluginInput(plugin=PluginUninstallParams(name="nope"))
        )
        assert result.status == "error"

    def test_disable_then_enable(self) -> None:
        from tianshangcad.mcp.tools.plugin import (
            PluginDisableParams,
            PluginEnableParams,
        )

        _install()
        disabled = cad_plugin(PluginInput(plugin=PluginDisableParams(name="mcp_test")))
        assert disabled.status == "success"
        enabled = cad_plugin(PluginInput(plugin=PluginEnableParams(name="mcp_test")))
        assert enabled.status == "success"


class TestListAndManifest:
    def test_list(self) -> None:
        _install()
        result = cad_plugin(PluginInput(plugin=PluginListParams()))
        assert result.status == "success"
        assert result.plugins[0]["name"] == "mcp_test"

    def test_list_discovers_official_plugins(self) -> None:
        result = cad_plugin(PluginInput(plugin=PluginListParams()))
        assert result.status == "success"
        names = {plugin["name"] for plugin in result.plugins}
        assert names >= {"gltf", "cam"}

    def test_manifest(self) -> None:
        _install()
        result = cad_plugin(
            PluginInput(plugin=PluginManifestParams(name="mcp_test"))
        )
        assert result.status == "success"
        assert result.manifest is not None
        assert result.manifest["version"] == "1.0.0"

    def test_manifest_unknown_returns_error(self) -> None:
        result = cad_plugin(
            PluginInput(plugin=PluginManifestParams(name="nope"))
        )
        assert result.status == "error"
