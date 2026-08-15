"""Plugin management tools (install / uninstall / list / enable / disable / manifest)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from tianshangcad.core.plugins import PluginManager
from tianshangcad.utils.errors import PluginError


class PluginInstallParams(BaseModel):
    """Install a plugin from a ``module:attr`` reference."""

    action: Literal["install"] = "install"
    entry_point: str = Field(
        ...,
        description="module:attr reference to the CADPlugin subclass",
        examples=["tianshangcad.plugins.gltf:GLTFPlugin"],
    )
    enable: bool = Field(True, description="Enable the plugin after install")


class PluginUninstallParams(BaseModel):
    """Uninstall a plugin by name."""

    action: Literal["uninstall"] = "uninstall"
    name: str = Field(..., description="Plugin name to uninstall")


class PluginListParams(BaseModel):
    """List installed plugins (triggers entry-point discovery)."""

    action: Literal["list"] = "list"


class PluginEnableParams(BaseModel):
    """Enable an installed plugin."""

    action: Literal["enable"] = "enable"
    name: str = Field(..., description="Plugin name to enable")


class PluginDisableParams(BaseModel):
    """Disable an installed plugin."""

    action: Literal["disable"] = "disable"
    name: str = Field(..., description="Plugin name to disable")


class PluginManifestParams(BaseModel):
    """Return a plugin's manifest."""

    action: Literal["manifest"] = "manifest"
    name: str = Field(..., description="Plugin name")


PluginActionParams = Annotated[
    PluginInstallParams
    | PluginUninstallParams
    | PluginListParams
    | PluginEnableParams
    | PluginDisableParams
    | PluginManifestParams,
    Field(discriminator="action"),
]


class PluginInput(BaseModel):
    """Input for the aggregate plugin tool."""

    plugin: PluginActionParams = Field(
        ...,
        description=(
            "Plugin action, discriminated by `action`: install, uninstall, "
            "list, enable, disable or manifest."
        ),
    )


class PluginOutput(BaseModel):
    """Output of the aggregate plugin tool."""

    action: str = Field(..., description="Plugin action executed")
    name: str = Field("", description="Plugin name")
    plugins: list[dict[str, Any]] = Field(
        default_factory=list, description="Installed plugin summaries"
    )
    manifest: dict[str, Any] | None = Field(None, description="Plugin manifest")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _name_of(params: Any) -> str:
    """Return the ``name`` field of a plugin action (empty when absent)."""
    return getattr(params, "name", "") or ""


def cad_plugin(input: PluginInput) -> PluginOutput:
    """Install, uninstall, list, enable, disable or inspect plugins.

    聚合插件工具。按 ``action`` 派发：install / uninstall / list / enable /
    disable / manifest。
    - ``install``: 从 ``module:attr`` 引用加载并安装一个 ``CADPlugin``。
    - ``uninstall`` / ``enable`` / ``disable``: 按名字管理插件生命周期。
    - ``list``: 触发 entry-point 发现并列出已安装插件。
    - ``manifest``: 返回指定插件的静态声明（名称/版本/权限/依赖）。

    When not to use: 插件提供的实际建模能力应通过其注册的 MCP 工具直接调用；
    ``cad_plugin`` 只管理插件生命周期。
    """
    manager = PluginManager()
    params = input.plugin
    try:
        if params.action == "install":
            name = manager.install_reference(params.entry_point, enable=params.enable)
            return PluginOutput(
                action="install", name=name, status="success", message=f"Installed {name}"
            )
        if params.action == "uninstall":
            manager.uninstall(params.name)
            return PluginOutput(
                action="uninstall", name=params.name, status="success", message="Uninstalled"
            )
        if params.action == "enable":
            manager.enable(params.name)
            return PluginOutput(
                action="enable", name=params.name, status="success", message="Enabled"
            )
        if params.action == "disable":
            manager.disable(params.name)
            return PluginOutput(
                action="disable", name=params.name, status="success", message="Disabled"
            )
        if params.action == "manifest":
            manifest = manager.get_manifest(params.name)
            if manifest is None:
                return PluginOutput(
                    action="manifest",
                    name=params.name,
                    status="error",
                    message=f"Plugin '{params.name}' not found",
                )
            return PluginOutput(
                action="manifest",
                name=params.name,
                manifest=manifest.model_dump(mode="json"),
                status="success",
            )
        manager.discover()
        return PluginOutput(action="list", plugins=manager.list_plugins(), status="success")
    except PluginError as exc:
        return PluginOutput(
            action=params.action, name=_name_of(params), status="error", message=str(exc)
        )


TOOLS: list[tuple[str, Any]] = [
    ("cad_plugin", cad_plugin),
]
