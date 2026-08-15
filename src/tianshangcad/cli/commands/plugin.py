"""Plugin management commands: install, uninstall, list, enable, disable, manifest."""

from __future__ import annotations

import typer

from tianshangcad.cli.utils import catch_errors
from tianshangcad.core.plugins import PluginManager

app = typer.Typer(help="Plugin lifecycle management")


@app.command("install")
@catch_errors
def cmd_install(
    entry_point: str = typer.Argument(..., help="module:attr reference to the plugin"),
    enable: bool = typer.Option(True, "--enable/--no-enable", help="Enable after install"),
) -> None:
    """Install a plugin from a module:attr reference."""
    name = PluginManager().install_reference(entry_point, enable=enable)
    typer.echo(f"Installed plugin {name}")


@app.command("uninstall")
@catch_errors
def cmd_uninstall(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Uninstall a plugin."""
    PluginManager().uninstall(name)
    typer.echo(f"Uninstalled plugin {name}")


@app.command("enable")
@catch_errors
def cmd_enable(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Enable a plugin."""
    PluginManager().enable(name)
    typer.echo(f"Enabled plugin {name}")


@app.command("disable")
@catch_errors
def cmd_disable(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Disable a plugin."""
    PluginManager().disable(name)
    typer.echo(f"Disabled plugin {name}")


@app.command("list")
@catch_errors
def cmd_list() -> None:
    """List installed plugins (triggers entry-point discovery)."""
    manager = PluginManager()
    manager.discover()
    plugins = manager.list_plugins()
    if not plugins:
        typer.echo("No plugins installed")
        return
    for plugin in plugins:
        state = "enabled" if plugin["enabled"] else "disabled"
        typer.echo(
            f"{plugin['name']}  v{plugin['version']}  [{state}]  {plugin['description']}"
        )


@app.command("manifest")
@catch_errors
def cmd_manifest(name: str = typer.Argument(..., help="Plugin name")) -> None:
    """Show a plugin's manifest as JSON."""
    manifest = PluginManager().get_manifest(name)
    if manifest is None:
        typer.echo(f"Plugin '{name}' not found", err=True)
        raise typer.Exit(code=1)
    typer.echo(manifest.model_dump_json(indent=2))
