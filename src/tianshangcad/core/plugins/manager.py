"""Plugin manager: discovery, lifecycle and contribution aggregation.

:class:`PluginManager` is a process-wide singleton. It discovers plugins
through the ``tianshangcad.plugins`` entry-point group, validates each
plugin's permission declaration against the configured policy, drives the
``load -> initialize -> run -> shutdown`` lifecycle and aggregates the tools
/ commands / kernels / solvers contributed by *enabled* plugins so the MCP
server, CLI and kernel loader can merge them into their own registries.

Plugin code runs in-process (the same trust domain as the server); the
permission declaration is enforced as a static policy gate. Process-level
sandboxing for untrusted plugins is a future hardening step.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import dataclass
from typing import Any, ClassVar

from tianshangcad.core.plugins.sdk import CADPlugin, PluginManifest, PluginPermission
from tianshangcad.utils.errors import PluginError

_ENTRY_POINT_GROUP = "tianshangcad.plugins"

#: Official plugins bundled with the package. Frozen executables (PyInstaller)
#: carry no distribution metadata, so ``entry_points`` discovery finds nothing;
#: these ``module:attr`` references are imported directly as a fallback.
_BUILTIN_PLUGINS = (
    "tianshangcad.plugins.gltf.plugin:GLTFPlugin",
    "tianshangcad.plugins.cam.plugin:CAMPlugin",
)


@dataclass
class _PluginState:
    """A loaded plugin and its runtime state."""

    plugin: CADPlugin
    manifest: PluginManifest
    enabled: bool = False


class PluginManager:
    """Singleton registry and lifecycle manager for CAD plugins."""

    _instance: ClassVar[PluginManager | None] = None

    def __new__(cls) -> PluginManager:
        """Return the process-wide singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the singleton's state once."""
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._plugins: dict[str, _PluginState] = {}
        self._allowed: set[PluginPermission] = set(PluginPermission)
        self._discovered = False

    @classmethod
    def reset(cls) -> None:
        """Drop the singleton and its state (test helper)."""
        cls._instance = None

    # ------------------------------------------------------------------
    # Policy
    # ------------------------------------------------------------------

    def deny(self, permission: PluginPermission) -> None:
        """Remove ``permission`` from the allowlist (security hardening hook).

        Once denied, ``install`` rejects any plugin whose manifest requests
        that permission.
        """
        self._allowed.discard(permission)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[str]:
        """Discover and install plugins from the entry-point group.

        Returns the names installed. A plugin that fails to load raises
        :class:`PluginError` rather than being silently skipped.
        """
        if self._discovered:
            return [state.manifest.name for state in self._plugins.values()]
        self._discovered = True
        entry_points: list[Any] = []
        try:
            entry_points = list(importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP))
        except Exception:  # pragma: no cover - packaging metadata unavailable
            entry_points = []
        names: list[str] = []
        for entry_point in entry_points:
            try:
                loaded = entry_point.load()
            except Exception as exc:
                raise PluginError(
                    f"Failed to load plugin entry point '{entry_point.name}': {exc}",
                    code="plugin_load_failed",
                ) from exc
            plugin = self._coerce(loaded, entry_point.name)
            names.append(self.install(plugin))
        # Built-in fallback: frozen executables ship no entry-point metadata,
        # so import the official plugins directly (skipped when already loaded).
        for reference in _BUILTIN_PLUGINS:
            try:
                plugin = self._load_reference(reference)
            except PluginError:
                continue
            if plugin.manifest.name not in self._plugins:
                names.append(self.install(plugin))
        return names

    @staticmethod
    def _coerce(loaded: Any, name: str) -> CADPlugin:
        """Turn an entry-point payload into a :class:`CADPlugin` instance."""
        if isinstance(loaded, CADPlugin):
            return loaded
        if isinstance(loaded, type) and issubclass(loaded, CADPlugin):
            return loaded()
        raise PluginError(
            f"Entry point '{name}' does not provide a CADPlugin subclass",
            code="plugin_invalid",
        )

    def _load_reference(self, reference: str) -> CADPlugin:
        """Import a ``module:attr`` reference and return a :class:`CADPlugin`."""
        module_name, sep, attr = reference.partition(":")
        if not sep or not module_name or not attr:
            raise PluginError(
                f"Invalid plugin reference '{reference}' (expected module:attr)",
                code="plugin_invalid",
            )
        try:
            module = importlib.import_module(module_name)
            loaded = getattr(module, attr)
        except Exception as exc:
            raise PluginError(
                f"Failed to load plugin '{reference}': {exc}", code="plugin_load_failed"
            ) from exc
        return self._coerce(loaded, module_name)

    def install_reference(self, reference: str, *, enable: bool = True) -> str:
        """Load a plugin from a ``module:attr`` reference and install it.

        ``reference`` points at a :class:`CADPlugin` subclass (or instance),
        e.g. ``tianshangcad.plugins.gltf:GLTFPlugin``.
        """
        return self.install(self._load_reference(reference), enable=enable)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def install(self, plugin: CADPlugin, *, enable: bool = True) -> str:
        """Validate, load and (optionally) enable a plugin.

        Returns the plugin name. Raises :class:`PluginError` on a duplicate
        name or a denied permission.
        """
        manifest = plugin.manifest
        if manifest.name in self._plugins:
            raise PluginError(
                f"Plugin '{manifest.name}' is already installed", code="plugin_exists"
            )
        self._validate_permissions(manifest)
        self._plugins[manifest.name] = _PluginState(plugin=plugin, manifest=manifest)
        plugin.load()
        plugin.initialize()
        if enable:
            self.enable(manifest.name)
        return manifest.name

    def uninstall(self, name: str) -> None:
        """Shut down and remove a plugin by name."""
        state = self._require(name)
        if state.enabled:
            state.plugin.shutdown()
        del self._plugins[name]

    def enable(self, name: str) -> None:
        """Activate an installed plugin (runs its ``run`` hook)."""
        state = self._require(name)
        if state.enabled:
            return
        self._check_dependencies(state.manifest)
        state.plugin.run()
        state.enabled = True

    def disable(self, name: str) -> None:
        """Deactivate a plugin (runs its ``shutdown`` hook)."""
        state = self._require(name)
        if not state.enabled:
            return
        state.plugin.shutdown()
        state.enabled = False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_plugins(self) -> list[dict[str, Any]]:
        """Return a summary dict for every installed plugin."""
        return [
            {
                "name": state.manifest.name,
                "version": state.manifest.version,
                "description": state.manifest.description,
                "author": state.manifest.author,
                "enabled": state.enabled,
                "permissions": [permission.value for permission in state.manifest.permissions],
                "dependencies": list(state.manifest.dependencies),
            }
            for state in self._plugins.values()
        ]

    def get_manifest(self, name: str) -> PluginManifest | None:
        """Return a plugin's manifest, or ``None`` when not installed."""
        state = self._plugins.get(name)
        return state.manifest if state else None

    # ------------------------------------------------------------------
    # Contribution aggregation
    # ------------------------------------------------------------------

    def tools(self) -> list[tuple[str, Any]]:
        """Return MCP tools contributed by enabled plugins (``(name, fn)``)."""
        result: list[tuple[str, Any]] = []
        for state in self._enabled():
            if PluginPermission.TOOLS not in state.manifest.permissions:
                continue
            registry: dict[str, Any] = {}
            state.plugin.register_tools(registry)
            result.extend(registry.items())
        return result

    def commands(self) -> list[tuple[str, Any]]:
        """Return CLI sub-apps contributed by enabled plugins (``(name, app)``)."""
        result: list[tuple[str, Any]] = []
        for state in self._enabled():
            if PluginPermission.COMMANDS not in state.manifest.permissions:
                continue
            registry: dict[str, Any] = {}
            state.plugin.register_commands(registry)
            result.extend(registry.items())
        return result

    def kernels(self) -> dict[str, Any]:
        """Return kernel factories contributed by enabled plugins (``name -> fn``)."""
        result: dict[str, Any] = {}
        for state in self._enabled():
            if PluginPermission.KERNEL not in state.manifest.permissions:
                continue
            registry: dict[str, Any] = {}
            state.plugin.register_kernel(registry)
            result.update(registry)
        return result

    def solvers(self) -> dict[str, Any]:
        """Return solver callables contributed by enabled plugins (``name -> fn``)."""
        result: dict[str, Any] = {}
        for state in self._enabled():
            if PluginPermission.SOLVER not in state.manifest.permissions:
                continue
            registry: dict[str, Any] = {}
            state.plugin.register_solver(registry)
            result.update(registry)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _require(self, name: str) -> _PluginState:
        state = self._plugins.get(name)
        if state is None:
            raise PluginError(f"Plugin '{name}' is not installed", code="plugin_not_found")
        return state

    def _enabled(self) -> list[_PluginState]:
        return [state for state in self._plugins.values() if state.enabled]

    def _validate_permissions(self, manifest: PluginManifest) -> None:
        for permission in manifest.permissions:
            if permission not in self._allowed:
                raise PluginError(
                    f"Plugin '{manifest.name}' requests denied permission "
                    f"'{permission.value}'",
                    code="permission_denied",
                )

    def _check_dependencies(self, manifest: PluginManifest) -> None:
        for dependency in manifest.dependencies:
            state = self._plugins.get(dependency)
            if state is None:
                raise PluginError(
                    f"Plugin '{manifest.name}' requires missing plugin '{dependency}'",
                    code="missing_dependency",
                )
            if not state.enabled:
                self.enable(dependency)
