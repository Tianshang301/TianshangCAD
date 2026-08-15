"""Unit tests for the plugin SDK and manager."""

from __future__ import annotations

from typing import Any

import pytest

from tianshangcad.core.plugins import (
    CADPlugin,
    PluginManager,
    PluginManifest,
    PluginPermission,
)
from tianshangcad.utils.errors import PluginError


def _echo() -> dict[str, bool]:
    return {"ok": True}


class _RecordingPlugin(CADPlugin):
    """A plugin that records lifecycle calls and registers a tool + command."""

    manifest = PluginManifest(
        name="recording",
        version="1.0.0",
        description="Recording plugin",
        permissions=[PluginPermission.TOOLS, PluginPermission.COMMANDS],
    )

    def __init__(self) -> None:
        self.events: list[str] = []

    def load(self) -> None:
        self.events.append("load")

    def initialize(self) -> None:
        self.events.append("initialize")

    def run(self) -> None:
        self.events.append("run")

    def shutdown(self) -> None:
        self.events.append("shutdown")

    def register_tools(self, registry: dict[str, Any]) -> None:
        registry["recording_echo"] = _echo

    def register_commands(self, registry: dict[str, Any]) -> None:
        registry["recording"] = object()


class _BackendPlugin(CADPlugin):
    """A plugin that declares the kernel and solver extension points."""

    manifest = PluginManifest(
        name="backend",
        version="0.1.0",
        permissions=[PluginPermission.KERNEL, PluginPermission.SOLVER],
    )

    def register_kernel(self, registry: dict[str, Any]) -> None:
        registry["custom"] = lambda: "kernel"

    def register_solver(self, registry: dict[str, Any]) -> None:
        registry["custom_solver"] = lambda: "solver"


class _DependentPlugin(CADPlugin):
    """A plugin that depends on a missing plugin."""

    manifest = PluginManifest(
        name="dependent",
        version="1.0.0",
        dependencies=["missing"],
        permissions=[PluginPermission.TOOLS],
    )


@pytest.fixture(autouse=True)
def _reset_manager() -> Any:
    """Reset the plugin manager singleton around every test."""
    PluginManager.reset()
    yield
    PluginManager.reset()


class TestLifecycle:
    """install / uninstall / enable / disable drive the lifecycle hooks."""

    def test_install_runs_load_initialize_run(self) -> None:
        plugin = _RecordingPlugin()
        PluginManager().install(plugin)
        assert plugin.events == ["load", "initialize", "run"]

    def test_install_without_enable_skips_run(self) -> None:
        plugin = _RecordingPlugin()
        PluginManager().install(plugin, enable=False)
        assert plugin.events == ["load", "initialize"]

    def test_duplicate_install_raises(self) -> None:
        PluginManager().install(_RecordingPlugin())
        with pytest.raises(PluginError):
            PluginManager().install(_RecordingPlugin())

    def test_uninstall_shuts_down_and_removes(self) -> None:
        plugin = _RecordingPlugin()
        manager = PluginManager()
        manager.install(plugin)
        manager.uninstall("recording")
        assert plugin.events == ["load", "initialize", "run", "shutdown"]
        assert manager.get_manifest("recording") is None

    def test_disable_then_enable(self) -> None:
        plugin = _RecordingPlugin()
        manager = PluginManager()
        manager.install(plugin)
        manager.disable("recording")
        assert "shutdown" in plugin.events
        manager.enable("recording")
        assert plugin.events.count("run") == 2

    def test_unknown_plugin_raises(self) -> None:
        with pytest.raises(PluginError):
            PluginManager().enable("nope")


class TestPermissions:
    """Permission declaration gates install."""

    def test_denied_permission_blocks_install(self) -> None:
        manager = PluginManager()
        manager.deny(PluginPermission.TOOLS)
        with pytest.raises(PluginError):
            manager.install(_RecordingPlugin())

    def test_allowed_permissions_install(self) -> None:
        assert PluginManager().install(_BackendPlugin()) == "backend"


class TestContributions:
    """Only enabled plugins contribute, and only declared extension points."""

    def test_tools_aggregated_from_enabled(self) -> None:
        manager = PluginManager()
        manager.install(_RecordingPlugin())
        assert dict(manager.tools()) == {"recording_echo": _echo}
        manager.disable("recording")
        assert manager.tools() == []

    def test_commands_aggregated(self) -> None:
        manager = PluginManager()
        manager.install(_RecordingPlugin())
        names = [name for name, _app in manager.commands()]
        assert names == ["recording"]

    def test_kernels_and_solvers_aggregated(self) -> None:
        manager = PluginManager()
        manager.install(_BackendPlugin())
        assert callable(manager.kernels()["custom"])
        assert callable(manager.solvers()["custom_solver"])

    def test_undeclared_extension_point_ignored(self) -> None:
        # _RecordingPlugin declares tools+commands but not kernel/solver.
        manager = PluginManager()
        manager.install(_RecordingPlugin())
        assert manager.kernels() == {}
        assert manager.solvers() == {}


class TestDependencies:
    """Dependency declaration gates enable."""

    def test_missing_dependency_blocks_enable(self) -> None:
        manager = PluginManager()
        with pytest.raises(PluginError):
            manager.install(_DependentPlugin())

    def test_dependency_auto_enabled(self) -> None:
        manager = PluginManager()
        manager.install(_BackendPlugin(), enable=False)

        class _NeedsBackend(CADPlugin):
            manifest = PluginManifest(
                name="needs_backend",
                version="1.0.0",
                dependencies=["backend"],
                permissions=[PluginPermission.TOOLS],
            )

        manager.install(_NeedsBackend())
        assert manager.get_manifest("backend") is not None


class TestIntrospection:
    """list / manifest reflect the installed plugins."""

    def test_list_plugins(self) -> None:
        manager = PluginManager()
        manager.install(_RecordingPlugin())
        plugins = manager.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "recording"
        assert plugins[0]["enabled"] is True
        assert plugins[0]["permissions"] == ["tools", "commands"]

    def test_get_manifest(self) -> None:
        manager = PluginManager()
        manager.install(_BackendPlugin())
        manifest = manager.get_manifest("backend")
        assert manifest is not None
        assert manifest.version == "0.1.0"


class TestInstallReference:
    """Loading a plugin from a module:attr reference."""

    def test_valid_reference(self) -> None:
        name = PluginManager().install_reference(f"{__name__}:_RecordingPlugin")
        assert name == "recording"

    def test_invalid_reference_raises(self) -> None:
        with pytest.raises(PluginError):
            PluginManager().install_reference("not_a_module:NoAttr")


class TestDiscovery:
    """Entry-point discovery installs plugins from the plugin group."""

    def test_discover_loads_entry_points(self, monkeypatch: Any) -> None:
        from importlib.metadata import EntryPoint

        entry_point = EntryPoint(
            name="recording",
            value=f"{__name__}:_RecordingPlugin",
            group="tianshangcad.plugins",
        )
        monkeypatch.setattr(
            "importlib.metadata.entry_points", lambda group: [entry_point]
        )
        names = PluginManager().discover()
        assert "recording" in names
        assert PluginManager().get_manifest("recording") is not None

    def test_discover_is_idempotent(self, monkeypatch: Any) -> None:
        from importlib.metadata import EntryPoint

        entry_point = EntryPoint(
            name="recording",
            value=f"{__name__}:_RecordingPlugin",
            group="tianshangcad.plugins",
        )
        monkeypatch.setattr(
            "importlib.metadata.entry_points", lambda group: [entry_point]
        )
        manager = PluginManager()
        manager.discover()
        # A second call must not double-install.
        first_count = len(manager.list_plugins())
        manager.discover()
        assert len(manager.list_plugins()) == first_count
