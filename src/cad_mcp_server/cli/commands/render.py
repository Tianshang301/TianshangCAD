"""Rendering output (planned for Phase 4+)."""

from __future__ import annotations

import typer

app = typer.Typer(help="Rendering output")


@app.command("status")
def cmd_status() -> None:
    """Show rendering subsystem status."""
    typer.echo("Rendering commands are planned for Phase 4.")
