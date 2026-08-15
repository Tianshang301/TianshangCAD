"""Unit tests for the cad_plugin aggregate tool."""

from __future__ import annotations

from typing import Any

import pytest

from tianshangcad.core.plugins import PluginManager
from tianshangcad.mcp.tools.plugin import (
    PluginDisableParams,
    PluginEnableParams,
    PluginInput,
    PluginInstallParams,
    PluginListParams,
    PluginManifestParams,
    PluginUninstallParams,
    cad_plugin,
)


@pytest.fixture(autouse=True)
def _reset_manager() -> Any:
    PluginManager.reset()
    yield
    PluginManager.reset()


def _install() -> None:
    cad_plugin(PluginInput(plugin=PluginInstallParams()))


class TestInstall:
    def test_install_discovers_official_plugins(self) -> None:
        result = cad_plugin(PluginInput(plugin=PluginInstallParams()))
        assert result.status == "success"
        names = {plugin["name"] for plugin in result.plugins}
        assert names >= {"gltf", "cam"}

    def test_install_is_idempotent(self) -> None:
        _install()
        result = cad_plugin(PluginInput(plugin=PluginInstallParams()))
        assert result.status == "success"
        assert len(result.plugins) == 2


class TestLifecycleActions:
    def test_uninstall(self) -> None:
        _install()
        result = cad_plugin(PluginInput(plugin=PluginUninstallParams(name="gltf")))
        assert result.status == "success"
        assert PluginManager().get_manifest("gltf") is None

    def test_uninstall_unknown_returns_error(self) -> None:
        result = cad_plugin(PluginInput(plugin=PluginUninstallParams(name="nope")))
        assert result.status == "error"

    def test_disable_then_enable(self) -> None:
        _install()
        disabled = cad_plugin(PluginInput(plugin=PluginDisableParams(name="gltf")))
        assert disabled.status == "success"
        enabled = cad_plugin(PluginInput(plugin=PluginEnableParams(name="gltf")))
        assert enabled.status == "success"


class TestListAndManifest:
    def test_list_after_install(self) -> None:
        _install()
        result = cad_plugin(PluginInput(plugin=PluginListParams()))
        assert result.status == "success"
        names = {plugin["name"] for plugin in result.plugins}
        assert names >= {"gltf", "cam"}

    def test_list_discovers_official_plugins(self) -> None:
        result = cad_plugin(PluginInput(plugin=PluginListParams()))
        assert result.status == "success"
        names = {plugin["name"] for plugin in result.plugins}
        assert names >= {"gltf", "cam"}

    def test_manifest(self) -> None:
        _install()
        result = cad_plugin(PluginInput(plugin=PluginManifestParams(name="gltf")))
        assert result.status == "success"
        assert result.manifest is not None
        assert result.manifest["version"] == "0.1.0"

    def test_manifest_unknown_returns_error(self) -> None:
        result = cad_plugin(PluginInput(plugin=PluginManifestParams(name="nope")))
        assert result.status == "error"
