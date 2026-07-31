"""Batch processing tools: synchronous execution and job scheduling."""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime
from typing import Any, get_type_hints

from pydantic import BaseModel, Field

from cad_mcp_server.mcp.tools._registry import get_registry
from cad_mcp_server.mcp.tools.status import log_event

# ---------------------------------------------------------------------------
# Job store
# ---------------------------------------------------------------------------

_jobs: dict[str, dict[str, Any]] = {}


def _new_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:8]}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


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

    commands: list[BatchCommand] = Field(..., description="Commands to schedule")
    name: str | None = Field(None, description="Job name")


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
    state: str = Field(..., description="Job state: pending / done / cancelled")
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        try:
            output = _dispatch(command.tool, dict(command.arguments))
            results.append(
                BatchResult(
                    tool=command.tool, index=index, success=True, result=output
                )
            )
        except Exception as exc:
            log_event("ERROR", "batch", f"{command.tool} failed: {exc}")
            results.append(
                BatchResult(
                    tool=command.tool, index=index, success=False, error=str(exc)
                )
            )
            if stop_on_error:
                break
    return results


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
    """Schedule a batch job for later execution."""
    job_id = _new_job_id()
    _jobs[job_id] = {
        "job_id": job_id,
        "name": input.name,
        "state": "pending",
        "created_at": _now(),
        "commands": [command.model_dump() for command in input.commands],
        "results": None,
    }
    return BatchScheduleOutput(
        job_id=job_id, status="success", message="Job scheduled"
    )


def cad_batch_status(input: BatchStatusInput) -> BatchStatusOutput:
    """Return the state of a scheduled batch job."""
    job = _jobs.get(input.job_id)
    if job is None:
        return BatchStatusOutput(
            job_id=input.job_id, name=None, state="unknown", created_at="",
            command_count=0, status="error", message=f"Job not found: {input.job_id}",
        )
    results = job.get("results")
    return BatchStatusOutput(
        job_id=job["job_id"],
        name=job["name"],
        state=job["state"],
        created_at=job["created_at"],
        command_count=len(job["commands"]),
        results=(
            [BatchResult.model_validate(item) for item in results] if results else None
        ),
        status="success",
    )


def cad_batch_cancel(input: BatchCancelInput) -> BatchCancelOutput:
    """Cancel a pending batch job."""
    job = _jobs.get(input.job_id)
    if job is None:
        return BatchCancelOutput(
            job_id=input.job_id, status="error", message=f"Job not found: {input.job_id}"
        )
    if job["state"] != "pending":
        return BatchCancelOutput(
            job_id=input.job_id,
            status="error",
            message=f"Cannot cancel job in state {job['state']}",
        )
    job["state"] = "cancelled"
    return BatchCancelOutput(
        job_id=input.job_id, status="success", message="Job cancelled"
    )


def cad_batch_list(input: BatchListInput) -> BatchListOutput:
    """List all batch jobs."""
    jobs = [
        {
            "job_id": job["job_id"],
            "name": job["name"],
            "state": job["state"],
            "created_at": job["created_at"],
            "command_count": len(job["commands"]),
        }
        for job in _jobs.values()
    ]
    return BatchListOutput(jobs=jobs, status="success")


TOOLS: list[tuple[str, Any]] = [
    ("cad_batch_execute", cad_batch_execute),
    ("cad_batch_schedule", cad_batch_schedule),
    ("cad_batch_status", cad_batch_status),
    ("cad_batch_cancel", cad_batch_cancel),
    ("cad_batch_list", cad_batch_list),
]
