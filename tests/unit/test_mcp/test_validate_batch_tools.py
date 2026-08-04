"""Validation, metrics and batch tool unit tests."""

from __future__ import annotations

import time

from tianshangcad.mcp.tools.batch import (
    BatchCancelInput,
    BatchCommand,
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
from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from tianshangcad.mcp.tools.status import (
    LogsGetInput,
    cad_logs_clear,
    cad_logs_get,
)
from tianshangcad.mcp.tools.validate import (
    MetricsGetInput,
    ValidateGeometryInput,
    ValidateInterferenceInput,
    ValidateTopologyInput,
    cad_metrics_get,
    cad_validate_geometry,
    cad_validate_interference,
    cad_validate_topology,
)

_METRICS = [BatchCommand(tool="cad_metrics_get", arguments={})]


def _wait_for(job_id: str, states: set[str], timeout: float = 5.0) -> str:
    """Poll until ``job_id`` reaches one of ``states`` or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = cad_batch_status(BatchStatusInput(job_id=job_id))
        if status.state in states:
            return status.state
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach {states}; got {status.state}")


def _seed_document() -> None:
    cad_file_create(FileCreateInput(filename="draw.json"))
    cad_object_create(
        ObjectCreateInput(
            type="box",
            params={"origin": [0, 0, 0], "dimensions": [10, 10, 10]},
            layer="0",
        )
    )
    cad_object_create(
        ObjectCreateInput(
            type="sphere",
            params={"center": [100, 100, 100], "radius": 5},
            layer="0",
        )
    )


class TestValidationTools:
    """Geometry validation tools."""

    def test_validate_geometry_ok(self) -> None:
        _seed_document()
        result = cad_validate_geometry(ValidateGeometryInput())
        assert result.status == "success"
        assert result.valid is True
        assert result.checked == 2

    def test_validate_geometry_missing_object(self) -> None:
        _seed_document()
        result = cad_validate_geometry(
            ValidateGeometryInput(object_ids=["does_not_exist"])
        )
        assert result.status == "error"

    def test_validate_topology(self) -> None:
        _seed_document()
        result = cad_validate_topology(ValidateTopologyInput())
        assert result.status == "success"
        assert result.object_count == 2
        assert result.kinds["box"] == 1
        assert result.kinds["sphere"] == 1

    def test_validate_interference(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [0, 0, 0], "dimensions": [10, 10, 10]},
                layer="0",
            )
        )
        cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [5, 5, 5], "dimensions": [10, 10, 10]},
                layer="0",
            )
        )
        result = cad_validate_interference(ValidateInterferenceInput())
        assert result.status == "success"
        assert result.interference_count == 1
        assert result.pairs[0].overlap["min"] == [5.0, 5.0, 5.0]

    def test_validate_interference_no_overlap(self) -> None:
        _seed_document()
        result = cad_validate_interference(ValidateInterferenceInput())
        assert result.status == "success"
        assert result.interference_count == 0

    def test_validate_interference_reports_volume(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [0, 0, 0], "dimensions": [10, 10, 10]},
                layer="0",
            )
        )
        cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [5, 5, 5], "dimensions": [10, 10, 10]},
                layer="0",
            )
        )
        result = cad_validate_interference(ValidateInterferenceInput())
        assert result.status == "success"
        assert result.interference_count == 1
        assert result.pairs[0].volume == 125.0
        assert result.total_volume == 125.0

    def test_validate_geometry_reports_structured_issue(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_object_create(
            ObjectCreateInput(
                type="polyline",
                params={"points": [[0, 0, 0], [1, 1, 0], [0, 1, 0], [1, 0, 0]]},
                layer="0",
            )
        )
        result = cad_validate_geometry(ValidateGeometryInput())
        assert result.status == "success"
        assert result.valid is False
        assert result.checked == 1
        assert len(result.issues) == 1
        issue = result.issues[0]
        assert issue.type == "self_intersection"
        assert issue.fix_suggestion
        assert issue.location is not None

    def test_validate_topology_summaries(self) -> None:
        cad_file_create(FileCreateInput(filename="draw.json"))
        cad_object_create(
            ObjectCreateInput(
                type="box",
                params={"origin": [0, 0, 0], "dimensions": [2, 3, 4]},
                layer="0",
            )
        )
        result = cad_validate_topology(ValidateTopologyInput())
        assert result.status == "success"
        assert result.object_count == 1
        assert len(result.summaries) == 1
        summary = result.summaries[0]
        assert summary.kind == "box"
        assert summary.vertices == 8
        assert summary.edges == 12
        assert summary.faces == 6
        assert summary.is_manifold is True
        assert result.warnings == []

    def test_validate_topology_warns_non_manifold_mesh(self) -> None:
        from tianshangcad.core.document import DocumentManager
        from tianshangcad.core.entity import EntityRecord

        cad_file_create(FileCreateInput(filename="draw.json"))
        record = EntityRecord(
            "mesh_1",
            "mesh",
            {
                "kind": "mesh",
                "params": {
                    "vertices": [
                        [0, 0, 0],
                        [1, 0, 0],
                        [0, 1, 0],
                        [0, 0, 1],
                        [0, -1, 0],
                    ],
                    "faces": [[0, 1, 2], [0, 1, 3], [1, 0, 4]],
                },
            },
            "0",
        )
        doc = DocumentManager().get_current()
        doc.entities._entities[record.id] = record
        result = cad_validate_topology(ValidateTopologyInput())
        assert result.status == "success"
        assert len(result.warnings) == 1
        assert "non-manifold" in result.warnings[0]
        assert result.summaries[0].non_manifold_edges == 1
        assert result.summaries[0].is_manifold is False

    def test_metrics_get(self) -> None:
        _seed_document()
        result = cad_metrics_get(MetricsGetInput())
        assert result.status == "success"
        assert result.files == 1
        assert result.objects == 2
        assert result.kinds["box"] == 1


class TestBatchExecute:
    """Synchronous batch execution."""

    def test_execute_success(self) -> None:
        result = cad_batch_execute(
            BatchExecuteInput(
                commands=[
                    BatchCommand(
                        tool="cad_file_create",
                        arguments={"filename": "a.dwg", "unit": "mm"},
                    ),
                    BatchCommand(
                        tool="cad_object_create",
                        arguments={
                            "type": "circle",
                            "params": {"center": [1, 1, 0], "radius": 3},
                            "layer": "0",
                        },
                    ),
                ]
            )
        )
        assert result.status == "success"
        assert result.success_count == 2
        assert result.failed_count == 0
        assert result.results[0].result["file_id"].startswith("file_")

    def test_execute_unknown_tool(self) -> None:
        result = cad_batch_execute(
            BatchExecuteInput(
                commands=[BatchCommand(tool="cad_does_not_exist", arguments={})]
            )
        )
        assert result.status == "error"
        assert result.failed_count == 1
        assert "Unknown tool" in result.results[0].error

    def test_execute_stop_on_error(self) -> None:
        result = cad_batch_execute(
            BatchExecuteInput(
                stop_on_error=True,
                commands=[
                    BatchCommand(tool="cad_does_not_exist", arguments={}),
                    BatchCommand(tool="cad_does_not_exist_2", arguments={}),
                ],
            )
        )
        assert result.failed_count == 1

    def test_execute_emits_structured_logs(self) -> None:
        cad_logs_clear(LogsGetInput())
        cad_batch_execute(BatchExecuteInput(commands=_METRICS))
        logs = cad_logs_get(LogsGetInput(source="batch"))
        assert logs.total >= 1
        assert any(
            entry.details and entry.details.get("tool_name") == "cad_metrics_get"
            for entry in logs.logs
        )


class TestBatchSchedule:
    """Scheduling with cron, dependencies, templates and scripts."""

    def test_schedule_cron_pending(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(
                name="nightly",
                commands=_METRICS,
                cron_expression="0 2 * * *",
            )
        )
        assert scheduled.status == "success"
        status = cad_batch_status(BatchStatusInput(job_id=scheduled.job_id))
        assert status.state == "pending"
        assert status.name == "nightly"

    def test_schedule_invalid_cron_returns_error(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(commands=_METRICS, cron_expression="not a cron")
        )
        assert scheduled.status == "error"
        assert scheduled.job_id == ""

    def test_schedule_oneoff_executes(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(name="once", commands=_METRICS)
        )
        state = _wait_for(scheduled.job_id, {"done", "error"})
        assert state == "done"
        status = cad_batch_status(BatchStatusInput(job_id=scheduled.job_id))
        assert status.results is not None
        assert status.results[0].success is True

    def test_schedule_cron_cancel(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(commands=_METRICS, cron_expression="0 2 * * *")
        )
        cancelled = cad_batch_cancel(BatchCancelInput(job_id=scheduled.job_id))
        assert cancelled.status == "success"
        status = cad_batch_status(BatchStatusInput(job_id=scheduled.job_id))
        assert status.state == "cancelled"

    def test_schedule_dependency_chain(self) -> None:
        prereq = cad_batch_schedule(BatchScheduleInput(name="p", commands=_METRICS))
        dependent = cad_batch_schedule(
            BatchScheduleInput(
                name="d", commands=_METRICS, depends_on=[prereq.job_id]
            )
        )
        _wait_for(prereq.job_id, {"done", "error"})
        state = _wait_for(dependent.job_id, {"done", "error"})
        assert state == "done"

    def test_schedule_template(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(template="cleanup", cron_expression="0 2 * * *")
        )
        assert scheduled.status == "success"

    def test_schedule_script_wraps_command(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(
                script="import math\nprint(math.pi)",
                script_type="python",
                cron_expression="0 2 * * *",
            )
        )
        assert scheduled.status == "success"
        record = cad_batch_status(BatchStatusInput(job_id=scheduled.job_id))
        assert record.command_count == 1

    def test_schedule_unknown_template_returns_error(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(template="nope", cron_expression="0 2 * * *")
        )
        assert scheduled.status == "error"


class TestBatchQuery:
    """List / status / cancel edge cases."""

    def test_list_jobs(self) -> None:
        cad_batch_schedule(BatchScheduleInput(name="a", cron_expression="0 2 * * *"))
        listed = cad_batch_list(BatchListInput())
        assert listed.status == "success"
        assert len(listed.jobs) >= 1
        assert listed.jobs[0]["command_count"] == 1

    def test_batch_status_missing(self) -> None:
        status = cad_batch_status(BatchStatusInput(job_id="nope"))
        assert status.status == "error"

    def test_batch_cancel_missing(self) -> None:
        result = cad_batch_cancel(BatchCancelInput(job_id="nope"))
        assert result.status == "error"

    def test_batch_cancel_non_pending(self) -> None:
        scheduled = cad_batch_schedule(BatchScheduleInput(name="x", cron_expression="0 2 * * *"))
        cad_batch_cancel(BatchCancelInput(job_id=scheduled.job_id))
        result = cad_batch_cancel(BatchCancelInput(job_id=scheduled.job_id))
        assert result.status == "error"

    def test_batch_templates(self) -> None:
        result = cad_batch_templates(BatchTemplatesInput())
        assert result.status == "success"
        assert "cleanup" in result.templates


class TestBatchRunScript:
    """Sandboxed script execution tool."""

    def test_run_python(self) -> None:
        result = cad_batch_run_script(
            BatchRunScriptInput(
                script="import math\nprint(math.sqrt(25))", script_type="python"
            )
        )
        assert result.status == "success"
        assert result.ok is True
        assert result.stdout.strip() == "5.0"

    def test_run_blocks_import_os(self) -> None:
        result = cad_batch_run_script(
            BatchRunScriptInput(script="import os", script_type="python")
        )
        assert result.status == "error"
        assert result.ok is False
        assert result.blocked_imports

    def test_run_scr(self) -> None:
        result = cad_batch_run_script(
            BatchRunScriptInput(script="cad_metrics_get\ncad_status_check", script_type="scr")
        )
        assert result.ok is True
        assert result.success_count == 2

    def test_run_unsupported_type(self) -> None:
        result = cad_batch_run_script(
            BatchRunScriptInput(script="x", script_type="powershell")
        )
        assert result.status == "error"
        assert "script_type" in result.message

    def test_run_timeout(self) -> None:
        result = cad_batch_run_script(
            BatchRunScriptInput(
                script="import time\nwhile True: time.sleep(1)",
                script_type="python",
                timeout=1,
            )
        )
        assert result.timed_out is True
