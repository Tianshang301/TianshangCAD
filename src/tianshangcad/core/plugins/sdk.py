"""Plugin SDK: manifest, permissions and the plugin base class.

A plugin is a :class:`CADPlugin` subclass carrying a
:class:`PluginManifest`. The manifest declares the plugin's identity and the
permissions it needs (which extension points it contributes to). The plugin
overrides any of the four ``register_*`` methods to contribute:

- ``register_tools``    — MCP tool callables (``name -> callable``)
- ``register_commands`` — CLI ``typer.Typer`` sub-apps (``name -> app``)
- ``register_kernel``   — CAD kernel factories (``name -> factory``)
- ``register_solver``   — constraint solver callables (``name -> callable``)

and any of the four lifecycle hooks ``load`` / ``initialize`` / ``run`` /
``shutdown``. Every hook and extension point has a no-op default, so a
plugin only overrides what it needs.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class PluginPermission(StrEnum):
    """Capabilities a plugin may declare and exercise.

    The four values map one-to-one onto the four extension points. A plugin
    may only contribute to an extension point whose permission it declares;
    the manager refuses to load a plugin that requests a permission outside
    the configured policy (see :class:`PluginManager`).
    """

    TOOLS = "tools"
    COMMANDS = "commands"
    KERNEL = "kernel"
    SOLVER = "solver"


class PluginManifest(BaseModel):
    """Static declaration of a plugin's identity and permissions."""

    name: str = Field(..., description="Unique plugin name (kebab-case recommended)")
    version: str = Field(..., description="Semantic version")
    description: str = Field("", description="Short human-readable summary")
    author: str = Field("", description="Plugin author")
    permissions: list[PluginPermission] = Field(
        default_factory=list,
        description="Extension points the plugin contributes to",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Names of plugins that must load first",
    )


class CADPlugin:
    """Base class for all CAD plugins.

    Subclasses define a :class:`PluginManifest` as a class attribute and
    override the extension points / lifecycle hooks they need. Every hook and
    extension point has a no-op default, so a plugin only implements what it
    uses.
    """

    manifest: ClassVar[PluginManifest]

    # ------------------------------------------------------------------
    # Lifecycle (no-op defaults)
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Validate the manifest and prepare the plugin (called once on install)."""

    def initialize(self) -> None:
        """Wire up internal state after ``load`` and dependency resolution."""

    def run(self) -> None:
        """Start the plugin's runtime (called on enable)."""

    def shutdown(self) -> None:
        """Release resources (called on disable / uninstall)."""

    # ------------------------------------------------------------------
    # Extension points (no-op defaults)
    # ------------------------------------------------------------------

    def register_tools(self, registry: dict[str, Any]) -> None:
        """Add MCP tool callables to ``registry`` keyed by tool name."""

    def register_commands(self, registry: dict[str, Any]) -> None:
        """Add CLI ``typer.Typer`` sub-apps to ``registry`` keyed by name."""

    def register_kernel(self, registry: dict[str, Any]) -> None:
        """Add CAD kernel factories to ``registry`` keyed by runtime name."""

    def register_solver(self, registry: dict[str, Any]) -> None:
        """Add constraint solver callables to ``registry`` keyed by name."""
