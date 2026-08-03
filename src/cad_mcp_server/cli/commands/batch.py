"""Batch processing commands: schedule, run scripts, list, status, cancel."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import typer

from cad_mcp_server.cli.utils import catch_errors, fail
from cad_mcp_server.mcp.tools.batch import (
    BatchCancelInput,
    BatchExecuteInput,
    BatchListInput,
    BatchRunScriptInput,
    BatchScheduleInput,
    BatchStatusInput,
    BatchTemplatesInput,
    cad_batch_cancel,
    cad_batch_execute,
    cad_batch_list,
    cad_batch_run_script,
    cad_batch_schedule,
    cad_batch_status,
    cad_batch_templates,
)
from cad_mcp_server.mcp.tools.crud import FileCreateInput, cad_file_create

app = typer.Typer(help="Batch processing")

_TERMINAL_STATES = ("done", "error", "cancelled")


def _print_results(results: Any) -> None:
    """Print per-command results in a compact table."""
    if not results:
        return
    for item in results:
        mark = "ok " if item.success else "ERR"
        detail = item.error or "done"
        typer.echo(f"  [{item.index}] {mark} {item.tool}: {detail}")


def _load_commands(path: str) -> list[dict[str, Any]]:
    """Load a JSON array of ``{tool, arguments}`` from ``path``."""
    target = Path(path)
    if not target.is_file():
        fail(f"Command file not found: {path}")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path}: {exc}")
    if not isinstance(data, list):
        fail("Command file must contain a JSON array of {tool, arguments}")
    return data


@app.command("schedule")
@catch_errors
def cmd_schedule(
    commands_file: str = typer.Argument(
        ..., help="JSON file with an array of {tool, arguments}"
    ),
    name: str | None = typer.Option(None, "--name", help="Job name"),
    cron: str | None = typer.Option(
        None, "--cron", help="Cron expression, e.g. '0 2 * * *'"
    ),
    depends_on: str | None = typer.Option(
        None, "--depends-on", help="Comma separated prerequisite job ids"
    ),
    webhook_url: str | None = typer.Option(
        None, "--webhook-url", help="URL to notify on completion"
    ),
    wait: bool = typer.Option(
        False,
        "--wait",
        help="Keep the CLI alive until a one-off (non-cron) job completes",
    ),
    timeout: float = typer.Option(
        120.0, "--timeout", help="Maximum seconds to wait before giving up (with --wait)"
    ),
) -> None:
    """Schedule a batch job from a commands JSON file.

    Without ``--cron`` the job runs once. ``--wait`` keeps the process
    alive until that one-shot job reaches a terminal state, so the job is
    guaranteed to actually execute in CLI mode.
    """
    commands = _load_commands(commands_file)
    from cad_mcp_server.mcp.tools.batch import BatchCommand

    result = cad_batch_schedule(
        BatchScheduleInput(
            commands=[BatchCommand.model_validate(command) for command in commands],
            name=name,
            cron_expression=cron,
            depends_on=depends_on.split(",") if depends_on else None,
            webhook_url=webhook_url,
        )
    )
    if result.status == "error":
        fail(result.message or "Failed to schedule job")
    typer.echo(f"Scheduled {result.job_id}: {result.message}")

    if not wait:
        return
    if cron:
        typer.echo("--wait is only valid for one-off (non-cron) jobs")
        return

    deadline = time.monotonic() + timeout
    while True:
        status = cad_batch_status(BatchStatusInput(job_id=result.job_id))
        if status.state in _TERMINAL_STATES:
            typer.echo(f"Job {result.job_id} finished: {status.state}")
            _print_results(status.results)
            if status.state != "done":
                raise typer.Exit(code=1)
            return
        if time.monotonic() >= deadline:
            typer.echo(f"Timed out waiting for job {result.job_id} (state: {status.state})")
            raise typer.Exit(code=1)
        time.sleep(0.2)


@app.command("run")
@catch_errors
def cmd_run(
    commands_file: str = typer.Argument(
        ..., help="JSON file with an array of {tool, arguments}"
    ),
    stop_on_error: bool = typer.Option(
        False, "--stop-on-error", help="Stop execution on the first error"
    ),
) -> None:
    """Execute a commands JSON file synchronously (one-shot, no scheduler)."""
    commands = _load_commands(commands_file)
    from cad_mcp_server.mcp.tools.batch import BatchCommand

    result = cad_batch_execute(
        BatchExecuteInput(
            commands=[BatchCommand.model_validate(command) for command in commands],
            stop_on_error=stop_on_error,
        )
    )
    if result.results:
        for item in result.results:
            mark = "ok " if item.success else "ERR"
            detail = item.error or "done"
            typer.echo(f"  [{item.index}] {mark} {item.tool}: {detail}")
    typer.echo(result.message)
    if result.status != "success":
        raise typer.Exit(code=1)


@app.command("run-script")
@catch_errors
def cmd_run_script(
    script_file: str = typer.Argument(..., help="Path to the script file"),
    script_type: str = typer.Option(
        "python", "--type", "-t", help="Script type: python | scr | batch"
    ),
    timeout: int = typer.Option(60, "--timeout", help="Timeout in seconds"),
) -> None:
    """Run a script through the sandboxed script engine."""
    target = Path(script_file)
    if not target.is_file():
        fail(f"Script file not found: {script_file}")
    result = cad_batch_run_script(
        BatchRunScriptInput(
            script=target.read_text(encoding="utf-8"),
            script_type=script_type,
            timeout=timeout,
        )
    )
    if result.script_type == "python":
        if result.stdout:
            typer.echo(result.stdout)
        if result.stderr:
            typer.echo(result.stderr, err=True)
        if not result.ok:
            fail(result.message or "Script failed")
    else:
        typer.echo(f"{result.success_count} succeeded, {result.failed_count} failed")
        if not result.ok:
            fail(result.message or "Script failed")


@app.command("list")
def cmd_list() -> None:
    """List all batch jobs."""
    result = cad_batch_list(BatchListInput())
    if not result.jobs:
        typer.echo("No batch jobs")
        return
    typer.echo(f"{'JOB ID':<14} {'STATE':<10} {'NAME':<24} COMMANDS")
    for job in result.jobs:
        typer.echo(
            f"{job['job_id']:<14} {job['state']:<10} {(job['name'] or ''):<24} "
            f"{job['command_count']}"
        )


@app.command("status")
def cmd_status(job_id: str = typer.Argument(..., help="Job id")) -> None:
    """Show the status of a batch job."""
    result = cad_batch_status(BatchStatusInput(job_id=job_id))
    if result.status == "error":
        fail(result.message or "Job not found")
    typer.echo(f"Job: {result.job_id} ({result.name or 'unnamed'})")
    typer.echo(f"State: {result.state}")
    typer.echo(f"Created: {result.created_at}")
    typer.echo(f"Commands: {result.command_count}")
    _print_results(result.results)


@app.command("cancel")
def cmd_cancel(job_id: str = typer.Argument(..., help="Job id")) -> None:
    """Cancel a pending batch job."""
    result = cad_batch_cancel(BatchCancelInput(job_id=job_id))
    if result.status == "error":
        fail(result.message or "Cancel failed")
    typer.echo(f"Cancelled {result.job_id}")


@app.command("templates")
def cmd_templates() -> None:
    """List available batch command templates."""
    result = cad_batch_templates(BatchTemplatesInput())
    if not result.templates:
        typer.echo("No templates available")
        return
    typer.echo("Available templates:")
    for name in result.templates:
        typer.echo(f"  - {name}")


@app.command("logs")
def cmd_logs(
    source: str | None = typer.Option(None, "--source", help="Filter by source, e.g. batch"),
    job_id: str | None = typer.Option(None, "--job-id", help="Filter by job id"),
    level: str | None = typer.Option(
        None, "--level", help="Minimum level: INFO / WARNING / ERROR"
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum entries"),
) -> None:
    """Query structured batch logs."""
    from cad_mcp_server.mcp.tools.status import LogsGetInput, cad_logs_get

    result = cad_logs_get(LogsGetInput(source=source, job_id=job_id, level=level, limit=limit))
    if not result.logs:
        typer.echo("No log entries match")
        return
    for entry in result.logs:
        details = entry.details or {}
        extra = (
            f" job_id={details.get('job_id')}"
            f" tool={details.get('tool_name')}"
            f" dur={details.get('duration_ms')}ms"
        )
        typer.echo(f"{entry.timestamp} [{entry.level}] {entry.source}: {entry.message}{extra}")


@app.command("demo")
def cmd_demo() -> None:
    """Create a demo file to exercise batch scheduling."""
    cad_file_create(FileCreateInput(filename="batch_demo.json", unit="mm"))
    typer.echo("Created batch_demo.json (no objects yet). Use cad-cli batch run-script to test.")
