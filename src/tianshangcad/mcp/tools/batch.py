"""Batch processing tools: synchronous execution and job scheduling.

Scheduled jobs are backed by :mod:`tianshangcad.core.scheduler`, which
persists job state in SQLite (APScheduler ``SQLAlchemyJobStore``) so jobs
survive server restarts. Script execution is sandboxed by
:mod:`tianshangcad.core.script_runner`.
"""

from __future__ import annotations

import inspect
import time
import uuid
from datetime import UTC, datetime
from typing import Any, get_type_hints

from pydantic import BaseModel, Field

from tianshangcad.core.batch_templates import list_templates
from tianshangcad.core.scheduler import SchedulerService, get_scheduler
from tianshangcad.core.script_runner import run_script
from tianshangcad.mcp.tools._registry import get_registry
from tianshangcad.mcp.tools.status import log_event
from tianshangcad.utils.errors import SchedulerError

# ---------------------------------------------------------------------------
# Input / output models
# ---------------------------------------------------------------------------


class BatchCommand(BaseModel):
    """A single tool invocation inside a batch."""

    tool: str = Field(..., description="Tool name, e.g. cad_object_create")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Tool arguments")


class BatchExecuteInput(BaseModel):
    """Input for executing a batch of commands."""

    commands: list[BatchCommand] = Field(..., description="Commands to execute in order")
    stop_on_error: bool = Field(True, description="Stop execution on the first error")


class BatchResult(BaseModel):
    """Result of a single batch command."""

    tool: str = Field(..., description="Tool name")
    index: int = Field(..., description="Command index")
    success: bool = Field(..., description="Whether the command succeeded")
    result: dict[str, Any] | None = Field(None, description="Tool output")
    error: str | None = Field(None, description="Error message")


class BatchExecuteOutput(BaseModel):
    """Output for batch execution."""

    results: list[BatchResult] = Field(..., description="Per-command results")
    success_count: int = Field(..., description="Number of successful commands")
    failed_count: int = Field(..., description="Number of failed commands")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class BatchScheduleInput(BaseModel):
    """Input for scheduling a batch job."""

    commands: list[BatchCommand] = Field(
        default_factory=list, description="Commands to schedule"
    )
    name: str | None = Field(None, description="Job name")
    cron_expression: str | None = Field(
        None, description="Standard 5-field cron expression, e.g. '0 2 * * *'"
    )
    depends_on: list[str] | None = Field(
        None, description="Job ids that must finish successfully before this one runs"
    )
    webhook_url: str | None = Field(
        None, description="URL to POST a JSON notification on completion"
    )
    script: str | None = Field(None, description="Script content to run (python/scr/batch)")
    script_type: str | None = Field(
        None, description="Script type: python | scr | batch (default python)"
    )
    timeout: int = Field(60, description="Script timeout in seconds", ge=1, le=3600)
    template: str | None = Field(None, description="Batch template name to render")
    template_vars: dict[str, Any] = Field(
        default_factory=dict, description="Variables for template rendering"
    )


class BatchScheduleOutput(BaseModel):
    """Output for scheduling a batch job."""

    job_id: str = Field(..., description="Job id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class BatchStatusInput(BaseModel):
    """Input for checking a batch job."""

    job_id: str = Field(..., description="Job id")


class BatchStatusOutput(BaseModel):
    """Output for checking a batch job."""

    job_id: str = Field(..., description="Job id")
    name: str | None = Field(None, description="Job name")
    state: str = Field(
        ..., description="Job state: pending / running / done / error / cancelled / blocked"
    )
    created_at: str = Field(..., description="Creation timestamp")
    command_count: int = Field(..., description="Number of commands")
    results: list[BatchResult] | None = Field(None, description="Results when executed")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class BatchCancelInput(BaseModel):
    """Input for cancelling a batch job."""

    job_id: str = Field(..., description="Job id")


class BatchCancelOutput(BaseModel):
    """Output for cancelling a batch job."""

    job_id: str = Field(..., description="Job id")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class BatchListInput(BaseModel):
    """Input for listing batch jobs."""


class BatchListOutput(BaseModel):
    """Output for listing batch jobs."""

    jobs: list[dict[str, Any]] = Field(..., description="Job summaries")
    status: str = Field(..., description="Operation status")


class BatchTemplatesInput(BaseModel):
    """Input for listing batch templates."""


class BatchTemplatesOutput(BaseModel):
    """Output for listing batch templates."""

    templates: list[str] = Field(..., description="Available template names")
    status: str = Field(..., description="Operation status")


class BatchRunScriptInput(BaseModel):
    """Input for running a sandboxed script."""

    script: str = Field(..., description="Script content")
    script_type: str = Field("python", description="Script type: python | scr | batch")
    timeout: int = Field(60, description="Timeout in seconds", ge=1, le=3600)
    args: list[str] = Field(default_factory=list, description="Arguments for python scripts")


class BatchRunScriptOutput(BaseModel):
    """Output for running a sandboxed script."""

    ok: bool = Field(..., description="Whether the script completed successfully")
    script_type: str = Field(..., description="Script type that ran")
    results: list[BatchResult] | None = Field(None, description="Per-command results (scr/batch)")
    success_count: int | None = Field(None, description="Successful commands (scr/batch)")
    failed_count: int | None = Field(None, description="Failed commands (scr/batch)")
    stdout: str | None = Field(None, description="Captured stdout (python)")
    stderr: str | None = Field(None, description="Captured stderr (python)")
    exit_code: int | None = Field(None, description="Process exit code (python)")
    duration_ms: float = Field(..., description="Execution time in milliseconds")
    timed_out: bool = Field(False, description="Whether execution hit the timeout")
    blocked_imports: list[str] = Field(default_factory=list, description="Blocked imports (python)")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash(arguments: dict[str, Any]) -> str:
    """Return a stable fingerprint of command arguments."""
    import hashlib
    import json as _json

    payload = _json.dumps(arguments, sort_keys=True, default=str)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()  # noqa: S324 - non-crypto fingerprint


def _dispatch(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a registered tool with validated arguments."""
    registry = get_registry()
    fn = registry.get(tool_name)
    if fn is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    parameters = inspect.signature(fn).parameters
    if not parameters:
        result = fn()
    else:
        param_name = next(iter(parameters))
        input_model = get_type_hints(fn)[param_name]
        model = input_model(**arguments)
        result = fn(**{param_name: model})
    if isinstance(result, BaseModel):
        return result.model_dump()
    return {"result": result}


def _run_commands(
    commands: list[BatchCommand], stop_on_error: bool
) -> list[BatchResult]:
    results: list[BatchResult] = []
    for index, command in enumerate(commands):
        started = time.perf_counter()
        try:
            output = _dispatch(command.tool, dict(command.arguments))
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            log_event(
                "INFO",
                "batch",
                f"{command.tool} succeeded",
                tool_name=command.tool,
                duration_ms=duration_ms,
                input_hash=_hash(dict(command.arguments)),
                output_summary=_summarize(output),
                timestamp=_now(),
            )
            results.append(
                BatchResult(
                    tool=command.tool, index=index, success=True, result=output
                )
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            log_event(
                "ERROR",
                "batch",
                f"{command.tool} failed: {exc}",
                tool_name=command.tool,
                duration_ms=duration_ms,
                input_hash=_hash(dict(command.arguments)),
                output_summary="",
                timestamp=_now(),
            )
            results.append(
                BatchResult(
                    tool=command.tool, index=index, success=False, error=str(exc)
                )
            )
            if stop_on_error:
                break
    return results


def _summarize(value: Any, limit: int = 200) -> str:
    import json as _json

    try:
        return _json.dumps(value, default=str)[:limit]
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return str(value)[:limit]


def _scheduler() -> SchedulerService:
    return get_scheduler()


def _schedule_commands(
    scheduler: SchedulerService,
    input: BatchScheduleInput,
) -> list[dict[str, Any]]:
    """Build the command list for a scheduled job."""
    commands: list[dict[str, Any]] = []
    if input.template:
        from tianshangcad.core.batch_templates import render_template

        commands.extend(render_template(input.template, input.template_vars))
    commands.extend(
        {"tool": command.tool, "arguments": dict(command.arguments)}
        for command in input.commands
    )
    if input.script:
        commands.append(
            {
                "tool": "cad_batch_run_script",
                "arguments": {
                    "script": input.script,
                    "script_type": input.script_type or "python",
                    "timeout": input.timeout,
                },
            }
        )
    if not commands and input.cron_expression:
        commands.append({"tool": "cad_status_health", "arguments": {}})
    return commands


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def cad_batch_execute(input: BatchExecuteInput) -> BatchExecuteOutput:
    """Execute a batch of tool commands synchronously and in order."""
    results = _run_commands(input.commands, input.stop_on_error)
    successes = sum(1 for result in results if result.success)
    failures = len(results) - successes
    status = "success" if failures == 0 else "error"
    message = f"{successes} succeeded, {failures} failed" if failures else "All commands succeeded"
    return BatchExecuteOutput(
        results=results,
        success_count=successes,
        failed_count=failures,
        status=status,
        message=message,
    )


def cad_batch_schedule(input: BatchScheduleInput) -> BatchScheduleOutput:
    """Schedule a batch job (cron, dependency chain, webhook or one-off).

    Supports a standard 5-field ``cron_expression``. Without one the job
    runs once as soon as its prerequisites (``depends_on``) allow.
    """
    job_id = _new_job_id()
    try:
        commands = _schedule_commands(get_scheduler(), input)
        get_scheduler().schedule(
            job_id=job_id,
            name=input.name,
            commands=commands,
            cron_expression=input.cron_expression,
            depends_on=input.depends_on,
            webhook_url=input.webhook_url,
        )
    except SchedulerError as exc:
        return BatchScheduleOutput(
            job_id="", status="error", message=f"Failed to schedule job: {exc}"
        )
    log_event(
        "INFO",
        "batch",
        f"Job {job_id} scheduled",
        cron=input.cron_expression,
        depends_on=input.depends_on,
        command_count=len(commands),
        timestamp=_now(),
    )
    message = "Job scheduled"
    if input.cron_expression:
        message += f" with cron '{input.cron_expression}'"
    return BatchScheduleOutput(job_id=job_id, status="success", message=message)


def cad_batch_status(input: BatchStatusInput) -> BatchStatusOutput:
    """Return the state of a scheduled batch job."""
    record = get_scheduler().get_job(input.job_id)
    if record is None:
        return BatchStatusOutput(
            job_id=input.job_id, name=None, state="unknown", created_at="",
            command_count=0, status="error", message=f"Job not found: {input.job_id}",
        )
    results = record.get("results")
    return BatchStatusOutput(
        job_id=record["job_id"],
        name=record["name"],
        state=record["state"],
        created_at=record["created_at"],
        command_count=len(record.get("commands", [])),
        results=(
            [BatchResult.model_validate(item) for item in results] if results else None
        ),
        status="success",
    )


def cad_batch_cancel(input: BatchCancelInput) -> BatchCancelOutput:
    """Cancel a pending (or blocked) batch job."""
    outcome = get_scheduler().cancel(input.job_id)
    if outcome == "not_found":
        return BatchCancelOutput(
            job_id=input.job_id, status="error", message=f"Job not found: {input.job_id}"
        )
    if outcome == "invalid_state":
        return BatchCancelOutput(
            job_id=input.job_id,
            status="error",
            message="Cannot cancel job in its current state",
        )
    return BatchCancelOutput(
        job_id=input.job_id, status="success", message="Job cancelled"
    )


def cad_batch_list(input: BatchListInput) -> BatchListOutput:
    """List all batch jobs (persisted across restarts)."""
    return BatchListOutput(jobs=get_scheduler().list_jobs(), status="success")


def cad_batch_templates(input: BatchTemplatesInput) -> BatchTemplatesOutput:
    """List the available batch command templates."""
    return BatchTemplatesOutput(templates=list_templates(), status="success")


def cad_batch_run_script(input: BatchRunScriptInput) -> BatchRunScriptOutput:
    """Run a sandboxed batch script (python / scr / batch)."""
    try:
        result = run_script(
            script=input.script,
            script_type=input.script_type,
            timeout=input.timeout,
            args=input.args,
        )
    except SchedulerError as exc:
        return BatchRunScriptOutput(
            ok=False,
            script_type=input.script_type,
            duration_ms=0.0,
            status="error",
            message=str(exc),
        )
    results = result.get("results")
    status = "success" if result["ok"] else "error"
    message = result.get("error")
    if result["script_type"] == "python":
        if result["timed_out"]:
            message = result["stderr"]
        elif not result["ok"] and not result.get("blocked_imports"):
            message = result["stderr"] or "Script exited with a non-zero code"
    return BatchRunScriptOutput(
        ok=result["ok"],
        script_type=result["script_type"],
        results=(
            [BatchResult.model_validate(item) for item in results] if results else None
        ),
        success_count=result.get("success_count"),
        failed_count=result.get("failed_count"),
        stdout=result.get("stdout"),
        stderr=result.get("stderr"),
        exit_code=result.get("exit_code"),
        duration_ms=result.get("duration_ms", 0.0),
        timed_out=result.get("timed_out", False),
        blocked_imports=result.get("blocked_imports", []),
        status=status,
        message=message,
    )


TOOLS: list[tuple[str, Any]] = [
    ("cad_batch_execute", cad_batch_execute),
    ("cad_batch_schedule", cad_batch_schedule),
    ("cad_batch_status", cad_batch_status),
    ("cad_batch_cancel", cad_batch_cancel),
    ("cad_batch_list", cad_batch_list),
    ("cad_batch_templates", cad_batch_templates),
    ("cad_batch_run_script", cad_batch_run_script),
]
