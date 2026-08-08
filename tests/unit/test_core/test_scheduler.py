"""Unit tests for the batch scheduler service."""

from __future__ import annotations

import time

import pytest

from tianshangcad.core.scheduler import SchedulerService
from tianshangcad.utils.errors import SchedulerError

_METRICS = [
    {"tool": "cad_validate", "arguments": {"query": {"action": "metrics"}}}
]


def _wait_for(
    scheduler: SchedulerService, job_id: str, states: set[str], timeout: float = 5.0
) -> str:
    """Poll until ``job_id`` reaches one of ``states`` or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        record = scheduler.get_job(job_id)
        if record and record["state"] in states:
            return record["state"]
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach {states}; got {scheduler.get_job(job_id)}")


@pytest.fixture
def scheduler() -> SchedulerService:
    """Return an isolated in-memory scheduler service."""
    service = SchedulerService(jobstore_url=None)
    yield service
    service.shutdown()


class TestScheduleAndQuery:
    """Basic scheduling and querying behaviour."""

    def test_schedule_cron_job_pending(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(
            job_id="j1", name="nightly", commands=_METRICS, cron_expression="0 2 * * *"
        )
        record = scheduler.get_job("j1")
        assert record is not None
        assert record["state"] == "pending"
        assert record["recurring"] is True
        assert record["cron_expression"] == "0 2 * * *"

    def test_schedule_invalid_cron_rejected(self, scheduler: SchedulerService) -> None:
        with pytest.raises(SchedulerError):
            scheduler.schedule(
                job_id="bad", name="x", commands=_METRICS, cron_expression="not a cron"
            )

    def test_schedule_no_commands_rejected(self, scheduler: SchedulerService) -> None:
        with pytest.raises(SchedulerError):
            scheduler.schedule(job_id="empty", name="x", commands=[])

    def test_get_job_missing_returns_none(self, scheduler: SchedulerService) -> None:
        assert scheduler.get_job("nope") is None

    def test_list_jobs_sorted_newest_first(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(job_id="a", name="a", commands=_METRICS, cron_expression="0 2 * * *")
        scheduler.schedule(job_id="b", name="b", commands=_METRICS, cron_expression="0 3 * * *")
        jobs = scheduler.list_jobs()
        assert [job["job_id"] for job in jobs] == ["b", "a"]
        assert jobs[0]["command_count"] == 1

    def test_cancel_pending_job(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(job_id="j1", name="x", commands=_METRICS, cron_expression="0 2 * * *")
        assert scheduler.cancel("j1") == "cancelled"
        assert scheduler.get_job("j1")["state"] == "cancelled"

    def test_cancel_missing_job(self, scheduler: SchedulerService) -> None:
        assert scheduler.cancel("nope") == "not_found"

    def test_cancel_finished_job_rejected(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(job_id="j1", name="x", commands=_METRICS)
        _wait_for(scheduler, "j1", {"done", "error"})
        assert scheduler.cancel("j1") == "invalid_state"

    def test_oneoff_runs_immediately(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(job_id="j1", name="once", commands=_METRICS)
        state = _wait_for(scheduler, "j1", {"done", "error"})
        assert state == "done"
        record = scheduler.get_job("j1")
        assert record is not None
        assert record["results"] is not None
        assert record["results"][0]["success"] is True
        assert record["log"][0]["tool_name"] == "cad_validate"
        assert "duration_ms" in record["log"][0]
        assert "input_hash" in record["log"][0]


class TestDependencyChain:
    """Prerequisite gating and downstream release."""

    def test_dependent_blocks_until_prereq_done(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(job_id="prereq", name="p", commands=_METRICS)
        scheduler.schedule(
            job_id="dependent", name="d", commands=_METRICS, depends_on=["prereq"]
        )
        _wait_for(scheduler, "prereq", {"done", "error"})
        state = _wait_for(scheduler, "dependent", {"done", "error"})
        assert state == "done"

    def test_dependent_blocks_on_unsatisfied_prereq(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(
            job_id="dependent", name="d", commands=_METRICS, depends_on=["never"]
        )
        _wait_for(scheduler, "dependent", {"blocked"})
        assert scheduler.get_job("dependent")["state"] == "blocked"

    def test_cancel_blocked_job(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(
            job_id="dependent", name="d", commands=_METRICS, depends_on=["never"]
        )
        _wait_for(scheduler, "dependent", {"blocked"})
        assert scheduler.cancel("dependent") == "cancelled"
        assert scheduler.get_job("dependent")["state"] == "cancelled"


class TestWebhook:
    """Completion notification via HTTP POST."""

    def test_webhook_sent_on_completion(self, scheduler: SchedulerService, monkeypatch) -> None:
        import tianshangcad.core.scheduler as scheduler_module

        payloads: list[dict] = []

        def fake_webhook(url: str, payload: dict) -> None:
            payloads.append({"url": url, "payload": payload})

        monkeypatch.setattr(scheduler_module, "_send_webhook", fake_webhook)
        scheduler.schedule(
            job_id="j1", name="x", commands=_METRICS, webhook_url="https://example.com/hook"
        )
        _wait_for(scheduler, "j1", {"done", "error"})
        assert len(payloads) == 1
        assert payloads[0]["url"] == "https://example.com/hook"
        assert payloads[0]["payload"]["job_id"] == "j1"
        assert payloads[0]["payload"]["state"] == "done"


class TestPersistence:
    """Job records survive a service restart via the JSON records file."""

    def test_records_persist_across_restart(self, tmp_path) -> None:
        url = f"sqlite:///{tmp_path / 'jobs.sqlite'}"
        first = SchedulerService(jobstore_url=url)
        first.schedule(job_id="cron", name="c", commands=_METRICS, cron_expression="0 2 * * *")
        first.schedule(job_id="once", name="o", commands=_METRICS)
        _wait_for(first, "once", {"done", "error"})
        first.cancel("cron")
        first.shutdown()

        second = SchedulerService(jobstore_url=url)
        try:
            assert second.get_job("cron")["state"] == "cancelled"
            assert second.get_job("once")["state"] == "done"
            assert {job["job_id"] for job in second.list_jobs()} == {"cron", "once"}
        finally:
            second.shutdown()

    def test_records_file_written(self, tmp_path) -> None:
        url = f"sqlite:///{tmp_path / 'jobs.sqlite'}"
        service = SchedulerService(jobstore_url=url)
        service.schedule(
            job_id="j1", name="x", commands=_METRICS, cron_expression="0 2 * * *"
        )
        service.shutdown()
        assert (tmp_path / "batch_jobs.json").is_file()

    def test_in_memory_mode_writes_no_file(self, scheduler: SchedulerService) -> None:
        scheduler.schedule(
            job_id="j1", name="x", commands=_METRICS, cron_expression="0 2 * * *"
        )
        assert scheduler._records_path() is None
