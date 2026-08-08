"""Status checks and in-memory logs for the MCP server."""

from __future__ import annotations

import time
from collections import deque
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from tianshangcad.core.document import DocumentManager
from tianshangcad.core.session import SessionManager
from tianshangcad.utils.errors import CADError

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

_SERVER_VERSION = "0.5.0"
_start_time = time.monotonic()

_LEVEL_ORDER = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}


def cad_status_check(input: StatusCheckInput) -> StatusCheckOutput:
    """Return an overall status summary of the current session."""
    # Deprecated, merged into cad_status (target=check)
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
    # Deprecated, merged into cad_status (target=file)
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
    # Deprecated, merged into cad_status (target=object)
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
    # Deprecated, merged into cad_status (target=layer)
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
    # Deprecated, merged into cad_status (target=health)
    from tianshangcad.mcp.tools._registry import get_registry

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
    # Deprecated, merged into cad_logs (action=get)
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
    # Deprecated, merged into cad_logs (action=clear)
    cleared = len(_log_buffer)
    _log_buffer.clear()
    return LogsClearOutput(cleared=cleared, status="success")


# ---------------------------------------------------------------------------
# Aggregate cad_status / cad_logs tools
# ---------------------------------------------------------------------------


class StatusCheckParams(BaseModel):
    """Overall session status summary."""

    target: Literal["check"] = Field("check", description="Query the overall session status")


class StatusFileParams(BaseModel):
    """Status of a file (defaults to current)."""

    target: Literal["file"] = Field("file", description="Query file status")
    file_id: str | None = Field(None, description="File id (defaults to current)")


class StatusObjectParams(BaseModel):
    """Status of a single object."""

    target: Literal["object"] = Field("object", description="Query object status")
    object_id: str = Field(..., description="Object id")


class StatusLayerParams(BaseModel):
    """Status of a layer including object count."""

    target: Literal["layer"] = Field("layer", description="Query layer status")
    name: str = Field(..., description="Layer name")


class StatusHealthParams(BaseModel):
    """Server health report."""

    target: Literal["health"] = Field("health", description="Query server health")


class StatusLogsGetParams(BaseModel):
    """Retrieve recent log entries."""

    target: Literal["logs_get"] = Field("logs_get", description="Read in-memory log entries")
    limit: int = Field(50, description="Maximum entries", ge=1, le=200)
    level: str | None = Field(None, description="Minimum level filter")
    source: str | None = Field(None, description="Source filter")
    job_id: str | None = Field(None, description="Job id filter")


class StatusLogsClearParams(BaseModel):
    """Clear the in-memory log buffer."""

    target: Literal["logs_clear"] = Field("logs_clear", description="Clear in-memory log entries")


StatusTargetParams = Annotated[
    StatusCheckParams
    | StatusFileParams
    | StatusObjectParams
    | StatusLayerParams
    | StatusHealthParams
    | StatusLogsGetParams
    | StatusLogsClearParams,
    Field(discriminator="target"),
]


class StatusInput(BaseModel):
    """Input for the aggregate status tool.

    聚合状态工具。``target`` 决定查询类型：
    - ``check``: 会话总体状态
    - ``file``: 文件状态（``file_id`` 可选）
    - ``object``: 对象状态（``object_id``）
    - ``layer``: 图层状态（``name``）
    - ``health``: 服务器健康报告
    - ``logs_get``: 读取内存日志
    - ``logs_clear``: 清空内存日志
    """

    status: StatusTargetParams = Field(
        default_factory=StatusCheckParams,
        description=(
            "Status query, discriminated by `target`: check, file, object, "
            "layer, health, logs_get or logs_clear."
        ),
    )


class StatusOutput(BaseModel):
    """Output of the aggregate status tool."""

    target: str = Field(..., description="Status target queried")
    summary: dict[str, Any] = Field(default_factory=dict, description="Status data")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def _health_report() -> dict[str, Any]:
    from tianshangcad.mcp.tools._registry import get_registry

    try:
        from tianshangcad import __version__
    except Exception:  # pragma: no cover - defensive
        __version__ = _SERVER_VERSION
    return {
        "ok": True,
        "version": __version__,
        "uptime_seconds": round(time.monotonic() - _start_time, 3),
        "tool_count": len(get_registry()),
    }


def cad_status(input: StatusInput) -> StatusOutput:
    """Query session, file, object, layer, health or logs status.

    按 ``target`` 查询当前会话的各类状态（check/file/object/layer/health/
    logs_get/logs_clear）。
    - ``check``: overall session summary (open files, current document).
    - ``file`` / ``object`` / ``layer``: live detail for one entity.
    - ``health``: server version, uptime and registered tool count.
    - ``logs_get`` / ``logs_clear``: read (with limit/level/source/job_id
      filters) or clear the in-memory log buffer.

    When not to use: ``cad_status`` reports live session/server state. For
    geometric *validation* (manifold checks, interference) or aggregate
    document statistics use ``cad_validate`` (geometry/metrics); for
    measuring distances/areas use ``cad_measure``.
    """
    params = input.status
    try:
        if params.target == "check":
            session = SessionManager().current_session
            current = session.current_file_id
            if current is None or current not in session.active_files:
                return StatusOutput(
                    target="check",
                    summary={
                        "files_open": len(session.active_files),
                        "current_file": None,
                        "objects": 0,
                        "layers": 0,
                    },
                    status="ok",
                )
            doc = session.active_files[current]
            return StatusOutput(
                target="check",
                summary={
                    "files_open": len(session.active_files),
                    "current_file": current,
                    "objects": doc.entities.count(),
                    "layers": len(doc.layers.list()),
                },
                status="ok",
            )

        if params.target == "file":
            info = DocumentManager().info(params.file_id)
            return StatusOutput(
                target="file",
                summary={
                    "file_id": info["file_id"],
                    "filename": info["filename"],
                    "unit": info["unit"],
                    "entity_count": info["entity_count"],
                    "dirty": info["dirty"],
                    "path": info["path"],
                },
                status="success",
            )

        if params.target == "object":
            doc = DocumentManager().get_current()
            record = doc.entities.read(params.object_id)
            return StatusOutput(
                target="object",
                summary={
                    "object_id": record.id,
                    "type": record.type,
                    "layer": record.layer,
                    "bbox": doc.entities.get_bbox(params.object_id),
                },
                status="success",
            )

        if params.target == "layer":
            doc = DocumentManager().get_current()
            layer = doc.layers.read(params.name)
            return StatusOutput(
                target="layer",
                summary={
                    "name": layer.name,
                    "visible": layer.visible,
                    "locked": layer.locked,
                    "object_count": len(doc.entities.list(layer=params.name)),
                },
                status="success",
            )

        if params.target == "logs_clear":
            cleared = len(_log_buffer)
            _log_buffer.clear()
            return StatusOutput(
                target="logs_clear",
                summary={"cleared": cleared},
                status="success",
                message=f"Cleared {cleared} log entries",
            )

        if params.target == "logs_get":
            entries = list(reversed(_log_buffer))
            if params.level is not None:
                minimum = _LEVEL_ORDER.get(params.level.upper(), 0)
                entries = [e for e in entries if _LEVEL_ORDER.get(e["level"], 0) >= minimum]
            if params.source is not None:
                entries = [e for e in entries if e.get("source") == params.source]
            if params.job_id is not None:
                entries = [e for e in entries if e.get("job_id") == params.job_id]
            selected = entries[: params.limit]
            return StatusOutput(
                target="logs_get",
                summary={
                    "logs": [
                        {
                            "timestamp": entry["timestamp"],
                            "level": entry["level"],
                            "source": entry["source"],
                            "message": entry["message"],
                            "details": {
                                key: value
                                for key, value in entry.items()
                                if key not in ("timestamp", "level", "source", "message")
                            },
                        }
                        for entry in selected
                    ],
                    "total": len(selected),
                },
                status="success",
            )

        return StatusOutput(target="health", summary=_health_report(), status="success")
    except CADError as exc:
        return StatusOutput(target=params.target, status="error", message=str(exc))


class LogsGetParams(BaseModel):
    """Retrieve recent log entries."""

    action: Literal["get"] = "get"
    limit: int = Field(50, description="Maximum entries", ge=1, le=200)
    level: str | None = Field(None, description="Minimum level filter")
    source: str | None = Field(None, description="Source filter")
    job_id: str | None = Field(None, description="Job id filter")


class LogsClearParams(BaseModel):
    """Clear the in-memory log buffer."""

    action: Literal["clear"] = "clear"


LogsActionParams = Annotated[LogsGetParams | LogsClearParams, Field(discriminator="action")]


class LogsInput(BaseModel):
    """Input for the aggregate logs tool.

    聚合日志工具。``action`` 为 ``get``（读取，支持 limit/level/source/job_id
    过滤）或 ``clear``（清空）。
    """

    logs: LogsActionParams = Field(
        default_factory=LogsGetParams,
        description=(
            "Log action, discriminated by `action`: get (read entries with "
            "limit/level/source/job_id filters) or clear."
        ),
    )


class LogsOutput(BaseModel):
    """Output of the aggregate logs tool."""

    action: str = Field(..., description="Log action")
    logs: list[dict[str, Any]] = Field(default_factory=list, description="Log entries")
    total: int = Field(0, description="Number of entries")
    cleared: int = Field(0, description="Number of cleared entries")
    status: str = Field(..., description="Operation status")
    message: str | None = Field(None, description="Status description")


def cad_logs(input: LogsInput) -> LogsOutput:
    """Read or clear the in-memory log buffer.

    按 ``action`` 读取（get）或清空（clear）内存日志。
    """
    # Deprecated, merged into cad_status (target=logs_get/logs_clear)
    params = input.logs
    if params.action == "clear":
        cleared = len(_log_buffer)
        _log_buffer.clear()
        return LogsOutput(action="clear", cleared=cleared, status="success")

    entries = list(reversed(_log_buffer))
    if params.level is not None:
        minimum = _LEVEL_ORDER.get(params.level.upper(), 0)
        entries = [entry for entry in entries if _LEVEL_ORDER.get(entry["level"], 0) >= minimum]
    if params.source is not None:
        entries = [entry for entry in entries if entry.get("source") == params.source]
    if params.job_id is not None:
        entries = [entry for entry in entries if entry.get("job_id") == params.job_id]
    selected = entries[: params.limit]
    return LogsOutput(
        action="get",
        logs=[
            {
                "timestamp": entry["timestamp"],
                "level": entry["level"],
                "source": entry["source"],
                "message": entry["message"],
                "details": {
                    key: value
                    for key, value in entry.items()
                    if key not in ("timestamp", "level", "source", "message")
                },
            }
            for entry in selected
        ],
        total=len(selected),
        status="success",
    )


TOOLS: list[tuple[str, Any]] = [
    ("cad_status", cad_status),
]
