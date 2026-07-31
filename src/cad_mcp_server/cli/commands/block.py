"""Blocks and parametrics (planned for a later phase)."""

from __future__ import annotations

import typer

app = typer.Typer(help="Blocks and parametrics")


@app.command("status")
def cmd_status() -> None:
    """Show block subsystem status."""
    typer.echo("Block commands are planned for Phase 5.")
