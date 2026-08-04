"""Batch job scheduling backed by APScheduler with durable job records.

Design
------
- APScheduler (``BackgroundScheduler``) owns *live* execution: cron triggers,
  one-shot fire times and worker threads. In production it uses a
  ``SQLAlchemyJobStore`` (``jobs.sqlite``) so live schedules auto-recover on
  restart.
- A separate *records* store keeps the authoritative history of every job
  (state, commands, results, per-command logs). APScheduler evicts one-shot
  jobs once they fire, so records are required to answer ``cad_batch_list`` /
  ``cad_batch_status`` with a consistent state, and to re-register cron jobs
  after a restart. Records are persisted to ``batch_jobs.json`` under the
  configured temp directory.

Test isolation is achieved by calling ``configure(jobstore_url=None)``, which
selects APScheduler's in-memory jobstore and disables file persistence.
"""

from __future__ import annotations

import atexit
import contextlib
import hashlib
import json
import time
import weakref
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from apscheduler.jobstores.memory import MemoryJobStore  # type: ignore[import-untyped]
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore  # type: ignore[import-untyped]
from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import-untyped]
from apscheduler.triggers.date import DateTrigger  # type: ignore[import-untyped]

from tianshangcad.utils.config import get_settings
from tianshangcad.utils.errors import SchedulerError

JOB_STATES = ("pending", "running", "done", "error", "cancelled", "blocked")
_RECURRING_STATES = ("pending", "blocked")

_UNSET = object()

# Weak registry of live scheduler services keyed by a per-instance id, so the
# APScheduler job function can dispatch back to the service that scheduled it.
_service_registry: dict[str, weakref.ReferenceType[SchedulerService]] = {}


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _input_hash(arguments: dict[str, Any]) -> str:
    """Return a stable md5 fingerprint of a command's arguments."""
    payload = json.dumps(arguments, sort_keys=True, default=str)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()  # noqa: S324 - non-crypto fingerprint


def _jobstore_url() -> str:
    """Return the ``sqlite:///`` URL used for production scheduling."""
    path = get_settings().temp_path / "jobs.sqlite"
    return f"sqlite:///{path}"


def _dispatch_command(tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke a registered MCP tool.

    Imported lazily to avoid a module-level circular import between
    ``core.scheduler`` and ``mcp.tools.batch``.
    """
    from tianshangcad.mcp.tools.batch import _dispatch

    return _dispatch(tool, arguments)


def _log_event(level: str, source: str, message: str, **details: Any) -> None:
    """Emit an event into the in-memory log ring buffer (lazy import)."""
    from tianshangcad.mcp.tools.status import log_event

    log_event(level, source, message, **details)


def _send_webhook(url: str, payload: dict[str, Any]) -> None:
    """POST a JSON payload to ``url`` without blocking job completion."""
    import httpx

    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(url, json=payload)
    except Exception as exc:  # pragma: no cover - network dependent
        _log_event("WARNING", "batch", f"Webhook failed: {exc}", url=url)


def _execute_job(job_id: str, metadata: dict[str, Any]) -> None:
    """APScheduler entry point: dispatch to the service that owns the job.

    Falls back to the singleton when the original service has been garbage
    collected (e.g. a durable job recovered after a restart).
    """
    service = None
    key = metadata.get("service_key")
    if key:
        ref = _service_registry.get(key)
        if ref is not None:
            service = ref()
    if service is None:
        service = get_scheduler()
    service._run_job(job_id, metadata)


class SchedulerService:
    """Scheduler singleton holding job records plus an APScheduler instance.

    The jobstore is chosen at ``configure()`` time: ``None`` selects the
    in-memory store and disables file persistence (unit tests); a ``sqlite://``
    URL enables durable scheduling.
    """

    def __init__(self, jobstore_url: Any = _UNSET) -> None:
        """Initialize the service without starting any scheduler."""
        self._configured_url: Any = jobstore_url
        self._service_key = f"scheduler-{id(self)}"
        _service_registry[self._service_key] = weakref.ref(self)
        self._scheduler: BackgroundScheduler | None = None
        self._records: dict[str, dict[str, Any]] = {}
        self._records_loaded = False
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def configure(self, jobstore_url: str | None) -> None:
        """Reconfigure the jobstore, dropping all job state."""
        with self._lock:
            self.shutdown()
            self._records = {}
            self._records_loaded = True
            self._configured_url = jobstore_url

    def _ensure_records_loaded(self) -> None:
        if not self._records_loaded:
            self._load_records()
            self._records_loaded = True

    @property
    def running(self) -> bool:
        """Whether the underlying scheduler is currently running."""
        return self._scheduler is not None and self._scheduler.running

    def _resolve_url(self) -> str | None:
        if self._configured_url is _UNSET:
            return _jobstore_url()
        value = self._configured_url
        if value is not None and not isinstance(value, str):
            return None  # pragma: no cover - defensive
        return value

    def _records_path(self) -> Path | None:
        """Return the records file path, co-located with the jobstore file."""
        url = self._resolve_url()
        if url is None:
            return None
        parent = Path(url.split(":///")[-1]).parent
        return parent / "batch_jobs.json"

    def _ensure_started(self) -> BackgroundScheduler:
        with self._lock:
            if self._scheduler is not None and self._scheduler.running:
                return self._scheduler
            url = self._resolve_url()
            if url is None:
                jobstores: dict[str, Any] = {"default": MemoryJobStore()}
            else:
                parent = Path(url.split(":///")[-1]).parent
                if str(parent) not in ("", "."):
                    parent.mkdir(parents=True, exist_ok=True)
                jobstores = {"default": SQLAlchemyJobStore(url=url)}
            scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")
            scheduler.start()
            self._scheduler = scheduler
            self._recover_jobs()
            return scheduler

    def _recover_jobs(self) -> None:
        """Re-register pending jobs into a freshly started scheduler."""
        scheduler = self._scheduler
        if scheduler is None:
            return
        for job_id, record in self._records.items():
            if record.get("state") not in _RECURRING_STATES:
                continue
            self._add_to_scheduler(scheduler, job_id, record)

    def shutdown(self) -> None:
        """Stop the scheduler and release its worker threads."""
        with self._lock:
            if self._scheduler is not None:
                with contextlib.suppress(Exception):
                    self._scheduler.shutdown(wait=False)
                self._scheduler = None

    def reset(self) -> None:
        """Shut down and drop all job state (used by tests)."""
        self.shutdown()

    # ------------------------------------------------------------------
    # Records persistence
    # ------------------------------------------------------------------

    def _load_records(self) -> None:
        path = self._records_path()
        if path is None:
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(data, dict):
            self._records = {
                job_id: record for job_id, record in data.items() if isinstance(record, dict)
            }

    def _save_records(self) -> None:
        path = self._records_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._records, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(path)

    # ------------------------------------------------------------------
    # Job storage helpers
    # ------------------------------------------------------------------

    def _metadata(self, job_id: str) -> dict[str, Any] | None:
        self._ensure_records_loaded()
        record = self._records.get(job_id)
        return dict(record) if record else None

    def _set_state(self, job_id: str, state: str, **fields: Any) -> None:
        record = self._records.get(job_id)
        if record is None:
            return
        record["state"] = state
        record.update(fields)
        self._save_records()

    def _add_to_scheduler(
        self,
        scheduler: BackgroundScheduler,
        job_id: str,
        record: dict[str, Any],
    ) -> None:
        cron = record.get("cron_expression")
        if cron:
            trigger: Any = CronTrigger.from_crontab(cron, timezone="UTC")
        else:
            trigger = DateTrigger(run_date=datetime.now(UTC))
        scheduler.add_job(
            _execute_job,
            trigger=trigger,
            id=job_id,
            kwargs={"job_id": job_id, "metadata": {**record, "service_key": self._service_key}},
            replace_existing=True,
        )

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def schedule(
        self,
        *,
        job_id: str,
        name: str | None,
        commands: list[dict[str, Any]],
        cron_expression: str | None = None,
        depends_on: list[str] | None = None,
        webhook_url: str | None = None,
    ) -> None:
        """Register a batch job and (re)start the scheduler.

        ``cron_expression`` accepts a standard 5-field cron expression. When
        absent the job runs once as soon as its prerequisites allow.
        """
        self._ensure_records_loaded()
        if not commands and cron_expression is None:
            raise SchedulerError("A scheduled job needs either commands or a cron expression")
        if cron_expression:
            try:
                CronTrigger.from_crontab(cron_expression, timezone="UTC")
            except (ValueError, TypeError) as exc:
                raise SchedulerError(f"Invalid cron expression: {cron_expression}") from exc
        scheduler = self._ensure_started()
        record: dict[str, Any] = {
            "job_id": job_id,
            "name": name,
            "state": "pending",
            "created_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "commands": commands,
            "results": None,
            "log": [],
            "depends_on": list(depends_on or []),
            "webhook_url": webhook_url,
            "cron_expression": cron_expression,
            "recurring": cron_expression is not None,
            "error": None,
        }
        self._records[job_id] = record
        self._save_records()
        self._add_to_scheduler(scheduler, job_id, record)

    # ------------------------------------------------------------------
    # Query / cancel
    # ------------------------------------------------------------------

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Return the full job record, or ``None`` if it does not exist."""
        return self._metadata(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        """Return summaries of every known job, newest creation first."""
        self._ensure_records_loaded()
        jobs = [
            {
                "job_id": record["job_id"],
                "name": record.get("name"),
                "state": record.get("state", "pending"),
                "created_at": record.get("created_at"),
                "command_count": len(record.get("commands", [])),
            }
            for record in reversed(self._records.values())
        ]
        jobs.sort(key=lambda item: str(item["created_at"]), reverse=True)
        return jobs

    def cancel(self, job_id: str) -> str:
        """Cancel a pending or blocked job, returning an outcome string.

        Outcomes: ``cancelled``, ``not_found``, ``invalid_state``.
        """
        self._ensure_records_loaded()
        record = self._records.get(job_id)
        if record is None:
            return "not_found"
        if record["state"] not in ("pending", "blocked"):
            return "invalid_state"
        self._set_state(job_id, "cancelled", finished_at=_now_iso())
        if self._scheduler is not None:
            with contextlib.suppress(Exception):
                self._scheduler.remove_job(job_id)
        _log_event("INFO", "batch", f"Job {job_id} cancelled")
        return "cancelled"

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _prereqs_satisfied(self, depends_on: list[str]) -> bool:
        if not depends_on:
            return True
        for prerequisite in depends_on:
            record = self._records.get(prerequisite)
            if record is None or record.get("state") != "done":
                return False
        return True

    def _run_job(self, job_id: str, metadata: dict[str, Any]) -> None:
        self._ensure_records_loaded()
        if self._records.get(job_id, {}).get("state") == "cancelled":
            return
        if not self._prereqs_satisfied(metadata.get("depends_on", [])):
            self._set_state(job_id, "blocked")
            return
        self._set_state(job_id, "running", started_at=_now_iso())
        results, logs, success_count, failed_count = self._execute_commands(
            job_id, metadata.get("commands", [])
        )
        state = "done" if failed_count == 0 else "error"
        self._set_state(
            job_id,
            state,
            results=results,
            log=logs,
            finished_at=_now_iso(),
            error=None if failed_count == 0 else f"{failed_count} command(s) failed",
        )
        if state == "done":
            self._release_dependents(job_id)
        webhook_url = metadata.get("webhook_url")
        if webhook_url:
            payload = {
                "job_id": job_id,
                "state": state,
                "completed_at": _now_iso(),
                "success_count": success_count,
                "failed_count": failed_count,
            }
            _send_webhook(webhook_url, payload)

    def _execute_commands(
        self, job_id: str, commands: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
        """Run commands, returning ``(results, logs, ok, failed)``."""
        results: list[dict[str, Any]] = []
        logs: list[dict[str, Any]] = []
        success_count = 0
        failed_count = 0
        for index, command in enumerate(commands):
            tool = command.get("tool", "")
            arguments = command.get("arguments", {})
            started = time.perf_counter()
            try:
                output = _dispatch_command(tool, arguments)
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                success_count += 1
                entry = {
                    "timestamp": _now_iso(),
                    "tool_name": tool,
                    "duration_ms": duration_ms,
                    "input_hash": _input_hash(arguments),
                    "output_summary": json.dumps(output, default=str)[:200],
                    "index": index,
                    "success": True,
                }
                results.append(
                    {"tool": tool, "index": index, "success": True, "result": output, "error": None}
                )
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started) * 1000, 3)
                failed_count += 1
                entry = {
                    "timestamp": _now_iso(),
                    "tool_name": tool,
                    "duration_ms": duration_ms,
                    "input_hash": _input_hash(arguments),
                    "output_summary": "",
                    "index": index,
                    "success": False,
                    "error": str(exc),
                }
                results.append(
                    {
                        "tool": tool,
                        "index": index,
                        "success": False,
                        "result": None,
                        "error": str(exc),
                    }
                )
            logs.append(entry)
            _log_event(
                "INFO" if entry["success"] else "ERROR",
                "batch",
                f"{tool} {'succeeded' if entry['success'] else 'failed'}",
                job_id=job_id,
                **entry,
            )
        return results, logs, success_count, failed_count

    def _release_dependents(self, completed_job_id: str) -> None:
        self._ensure_records_loaded()
        scheduler = self._scheduler
        if scheduler is None:
            return
        for job_id, record in self._records.items():
            if completed_job_id not in record.get("depends_on", []):
                continue
            if record.get("state") != "blocked":
                continue
            if self._prereqs_satisfied(record.get("depends_on", [])):
                self._add_to_scheduler(scheduler, job_id, record)
                _log_event("INFO", "batch", f"Released dependent job {job_id}")


_scheduler_instance: SchedulerService | None = None


def get_scheduler() -> SchedulerService:
    """Return the process-wide scheduler singleton."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
        _scheduler_instance._ensure_records_loaded()
        atexit.register(_scheduler_instance.shutdown)
    return _scheduler_instance
