"""Batch processing (planned for Phase 3)."""

from __future__ import annotations

import typer

app = typer.Typer(help="Batch processing")


@app.command("status")
def cmd_status() -> None:
    """Show batch subsystem status."""
    typer.echo("Batch commands are planned for Phase 3.")
