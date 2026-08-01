"""Status checks and in-memory logs for the MCP server."""

from __future__ import annotations

import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.core.session import SessionManager
from cad_mcp_server.utils.errors import CADError

# ---------------------------------------------------------------------------
# In-memory log ring buffer
# ---------------------------------------------------------------------------

_MAX_LOG_ENTRIES = 200
_log_buffer: deque[dict[str, Any]] = deque(maxlen=_MAX_LOG_ENTRIES)


def log_event(level: str, source: str, message: str, **details: Any) -> None:
    """Append an event to the in-memory ring buffer."""
    _log_buffer.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level.upper(),
            "source": source,
            "message": message,
            **details,
        }
    )


# ---------------------------------------------------------------------------
# Input / output models
# ---------------------------------------------------------------------------


class StatusCheckInput(BaseModel):
    """Input for a general status check."""


class StatusCheckOutput(BaseModel):
    """Output for a general status check."""

    files_open: int = Field(..., description="Number of open files")
    current_file: str | None = Field(None, description="Current file id")
    objects: int = Field(..., description="Number of objects in the current document")
    layers: int = Field(..., description="Number of layers in the current document")
    status: str = Field(..., description="Overall status: ok / error")


class StatusFileInput(BaseModel):
    """Input for checking the current file status."""

    file_id: str | None = Field(None, description="File id (defaults to current)")


class StatusFileOutput(BaseModel):
    """Output for file status."""

    file_id: str = Field(..., description="File id")
    filename: str = Field(..., description="File name")
    unit: str = Field(..., description="Document unit")
    entity_count: int = Field(..., description="Object count")
    dirty: bool = Field(..., description="Unsaved changes present")
    path: str | None = Field(None, description="Saved path")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class StatusObjectInput(BaseModel):
    """Input for checking an object's status."""

    object_id: str = Field(..., description="Object id")


class StatusObjectOutput(BaseModel):
    """Output for object status."""

    object_id: str = Field(..., description="Object id")
    type: str = Field(..., description="Object type")
    layer: str = Field(..., description="Layer name")
    bbox: dict[str, list[float]] = Field(..., description="Bounding box")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class StatusLayerInput(BaseModel):
    """Input for checking a layer's status."""

    name: str = Field(..., description="Layer name")


class StatusLayerOutput(BaseModel):
    """Output for layer status."""

    name: str = Field(..., description="Layer name")
    visible: bool = Field(..., description="Visibility")
    locked: bool = Field(..., description="Lock state")
    object_count: int = Field(..., description="Objects on the layer")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


class StatusHealthInput(BaseModel):
    """Input for a health check."""


class StatusHealthOutput(BaseModel):
    """Output for a health check."""

    ok: bool = Field(..., description="Server healthy flag")
    version: str = Field(..., description="Server version")
    uptime_seconds: float = Field(..., description="Seconds since server start")
    tool_count: int = Field(..., description="Number of registered tools")
    status: str = Field(..., description="Operation status")


class LogsGetInput(BaseModel):
    """Input for retrieving logs."""

    limit: int = Field(50, description="Maximum number of entries to return", ge=1, le=200)
    level: str | None = Field(None, description="Filter by minimum level (INFO/WARNING/ERROR)")
    source: str | None = Field(None, description="Filter by log source, e.g. batch")
    job_id: str | None = Field(None, description="Filter entries for a specific job id")


class LogEntry(BaseModel):
    """A single log entry."""

    timestamp: str = Field(..., description="ISO timestamp")
    level: str = Field(..., description="Log level")
    source: str = Field(..., description="Log source")
    message: str = Field(..., description="Log message")
    details: dict[str, Any] | None = Field(None, description="Structured log details")


class LogsGetOutput(BaseModel):
    """Output for retrieving logs."""

    logs: list[LogEntry] = Field(..., description="Log entries (newest first)")
    total: int = Field(..., description="Number of entries returned")
    status: str = Field(..., description="Operation status")


class LogsClearInput(BaseModel):
    """Input for clearing logs."""


class LogsClearOutput(BaseModel):
    """Output for clearing logs."""

    cleared: int = Field(..., description="Number of entries removed")
    status: str = Field(..., description="Operation status")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

_SERVER_VERSION = "0.2.5"
_start_time = time.monotonic()

_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


def cad_status_check(input: StatusCheckInput) -> StatusCheckOutput:
    """Return an overall status summary of the current session."""
    session = SessionManager().current_session
    current = session.current_file_id
    if current is None or current not in session.active_files:
        return StatusCheckOutput(
            files_open=len(session.active_files),
            current_file=None,
            objects=0,
            layers=0,
            status="ok",
        )
    doc = session.active_files[current]
    return StatusCheckOutput(
        files_open=len(session.active_files),
        current_file=current,
        objects=doc.entities.count(),
        layers=len(doc.layers.list()),
        status="ok",
    )


def cad_status_file(input: StatusFileInput) -> StatusFileOutput:
    """Return the status of a file (defaults to the current one)."""
    try:
        manager = DocumentManager()
        info = manager.info(input.file_id)
        return StatusFileOutput(
            file_id=info["file_id"],
            filename=info["filename"],
            unit=info["unit"],
            entity_count=info["entity_count"],
            dirty=info["dirty"],
            path=info["path"],
            status="success",
        )
    except CADError as exc:
        return StatusFileOutput(
            file_id="", filename="", unit="", entity_count=0, dirty=False, path=None,
            status="error", message=str(exc),
        )


def cad_status_object(input: StatusObjectInput) -> StatusObjectOutput:
    """Return the status of a single object."""
    try:
        doc = DocumentManager().get_current()
        record = doc.entities.read(input.object_id)
        bbox = doc.entities.get_bbox(input.object_id)
        return StatusObjectOutput(
            object_id=record.id,
            type=record.type,
            layer=record.layer,
            bbox=bbox,
            status="success",
        )
    except CADError as exc:
        return StatusObjectOutput(
            object_id="", type="", layer="",
            bbox={"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]},
            status="error", message=str(exc),
        )


def cad_status_layer(input: StatusLayerInput) -> StatusLayerOutput:
    """Return the status of a layer including its object count."""
    try:
        doc = DocumentManager().get_current()
        layer = doc.layers.read(input.name)
        count = len(doc.entities.list(layer=input.name))
        return StatusLayerOutput(
            name=layer.name,
            visible=layer.visible,
            locked=layer.locked,
            object_count=count,
            status="success",
        )
    except CADError as exc:
        return StatusLayerOutput(
            name="", visible=False, locked=False, object_count=0,
            status="error", message=str(exc),
        )


def cad_status_health(input: StatusHealthInput) -> StatusHealthOutput:
    """Return the server health report."""
    from cad_mcp_server.mcp.tools._registry import get_registry

    tool_count = len(get_registry())
    return StatusHealthOutput(
        ok=True,
        version=_SERVER_VERSION,
        uptime_seconds=round(time.monotonic() - _start_time, 3),
        tool_count=tool_count,
        status="success",
    )


def cad_logs_get(input: LogsGetInput) -> LogsGetOutput:
    """Return recent log entries (newest first), optionally filtered."""
    entries = list(reversed(_log_buffer))
    if input.level is not None:
        minimum = _LEVEL_ORDER.get(input.level.upper(), 0)
        entries = [
            entry for entry in entries if _LEVEL_ORDER.get(entry["level"], 0) >= minimum
        ]
    if input.source is not None:
        entries = [entry for entry in entries if entry.get("source") == input.source]
    if input.job_id is not None:
        entries = [entry for entry in entries if entry.get("job_id") == input.job_id]
    selected = entries[: input.limit]
    return LogsGetOutput(
        logs=[
            LogEntry(
                timestamp=entry["timestamp"],
                level=entry["level"],
                source=entry["source"],
                message=entry["message"],
                details={
                    key: value
                    for key, value in entry.items()
                    if key not in ("timestamp", "level", "source", "message")
                },
            )
            for entry in selected
        ],
        total=len(selected),
        status="success",
    )


def cad_logs_clear(input: LogsClearInput) -> LogsClearOutput:
    """Clear the in-memory log buffer."""
    cleared = len(_log_buffer)
    _log_buffer.clear()
    return LogsClearOutput(cleared=cleared, status="success")


TOOLS: list[tuple[str, Any]] = [
    ("cad_status_check", cad_status_check),
    ("cad_status_file", cad_status_file),
    ("cad_status_object", cad_status_object),
    ("cad_status_layer", cad_status_layer),
    ("cad_status_health", cad_status_health),
    ("cad_logs_get", cad_logs_get),
    ("cad_logs_clear", cad_logs_clear),
]
