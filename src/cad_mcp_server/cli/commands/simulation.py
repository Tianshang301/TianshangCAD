"""Simulation commands: mesh, setup, run, result, list.

Numerical arguments support ``{name}`` interpolation against the current
document's parametric variables.
"""

from __future__ import annotations

import typer

from cad_mcp_server.cli.utils import catch_errors
from cad_mcp_server.core.simulation import SimulationManager

app = typer.Typer(help="Simulation commands")


def _manager() -> SimulationManager:
    return SimulationManager()


def _echo_value(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


@app.command("mesh")
@catch_errors
def cmd_mesh(
    entity_id: str = typer.Argument(..., help="Entity id to mesh"),
    nx: int = typer.Option(4, "--nx", help="Divisions along X"),
    ny: int = typer.Option(4, "--ny", help="Divisions along Y"),
    nz: int = typer.Option(4, "--nz", help="Divisions along Z"),
) -> None:
    """Mesh an entity's bounding box into a hexa grid."""
    mesh = _manager().mesh(entity_id, nx, ny, nz)
    typer.echo(
        f"Mesh: {mesh['node_count']} nodes, {mesh['element_count']} "
        f"{mesh['element_type']} elements, volume {_echo_value(mesh['volume'])}"
    )


@app.command("setup")
@catch_errors
def cmd_setup(
    name: str = typer.Argument(..., help="Simulation name"),
    kind: str = typer.Option(
        ..., "--kind", "-k", help="Simulation kind: fea | kinematics"
    ),
    entity_id: str | None = typer.Option(None, "--entity", "-e", help="Target entity id"),
) -> None:
    """Register a simulation for later execution."""
    sim_id = _manager().create(name=name, kind=kind, entity_id=entity_id)
    typer.echo(f"Simulation {name} registered as {sim_id}")


@app.command("run")
@catch_errors
def cmd_run(
    sim_id: str = typer.Argument(..., help="Simulation id"),
    async_run: bool = typer.Option(False, "--async", help="Schedule via the batch subsystem"),
) -> None:
    """Run a registered simulation."""
    if async_run:
        job_id = _manager().submit(sim_id)
        typer.echo(f"Scheduled {sim_id} as async batch job {job_id}")
        return
    result = _manager().run(sim_id)
    state = result.status.value
    if state == "done":
        metrics = result.metrics
        typer.echo(f"{sim_id} {state}: {metrics}")
    else:
        typer.echo(f"{sim_id} {state}: {result.message}")


@app.command("result")
@catch_errors
def cmd_result(
    sim_id: str = typer.Argument(..., help="Simulation id"),
) -> None:
    """Print the current result of a simulation."""
    summary = _manager().result(sim_id)
    typer.echo(f"{summary['sim_id']} [{summary['kind']}] {summary['status']}")
    if summary["metrics"]:
        typer.echo(str(summary["metrics"]))
    if summary["message"]:
        typer.echo(summary["message"])


@app.command("list")
@catch_errors
def cmd_list() -> None:
    """List all registered simulations."""
    simulations = _manager().list()
    if not simulations:
        typer.echo("No simulations registered")
        return
    for summary in simulations:
        typer.echo(
            f"{summary['sim_id']:14s} {summary['name']:20s} "
            f"{summary['kind']:12s} {summary['status']}"
        )
