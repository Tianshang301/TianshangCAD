"""Validation, metrics and batch tool unit tests."""

from __future__ import annotations

from cad_mcp_server.mcp.tools.batch import (
    BatchCancelInput,
    BatchCommand,
    BatchExecuteInput,
    BatchListInput,
    BatchScheduleInput,
    BatchStatusInput,
    cad_batch_cancel,
    cad_batch_execute,
    cad_batch_list,
    cad_batch_schedule,
    cad_batch_status,
)
from cad_mcp_server.mcp.tools.crud import (
    FileCreateInput,
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)
from cad_mcp_server.mcp.tools.validate import (
    MetricsGetInput,
    ValidateGeometryInput,
    ValidateInterferenceInput,
    ValidateTopologyInput,
    cad_metrics_get,
    cad_validate_geometry,
    cad_validate_interference,
    cad_validate_topology,
)


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

    def test_metrics_get(self) -> None:
        _seed_document()
        result = cad_metrics_get(MetricsGetInput())
        assert result.status == "success"
        assert result.files == 1
        assert result.objects == 2
        assert result.kinds["box"] == 1


class TestBatchTools:
    """Batch processing tools."""

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

    def test_schedule_status_cancel_list(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(
                name="my-job",
                commands=[BatchCommand(tool="cad_metrics_get", arguments={})],
            )
        )
        assert scheduled.status == "success"
        job_id = scheduled.job_id

        status = cad_batch_status(BatchStatusInput(job_id=job_id))
        assert status.state == "pending"
        assert status.name == "my-job"
        assert status.command_count == 1

        listed = cad_batch_list(BatchListInput())
        assert any(job["job_id"] == job_id for job in listed.jobs)

        cancelled = cad_batch_cancel(BatchCancelInput(job_id=job_id))
        assert cancelled.status == "success"
        status = cad_batch_status(BatchStatusInput(job_id=job_id))
        assert status.state == "cancelled"

    def test_batch_status_missing(self) -> None:
        status = cad_batch_status(BatchStatusInput(job_id="nope"))
        assert status.status == "error"

    def test_batch_cancel_missing(self) -> None:
        result = cad_batch_cancel(BatchCancelInput(job_id="nope"))
        assert result.status == "error"

    def test_batch_cancel_non_pending(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(commands=[BatchCommand(tool="cad_metrics_get", arguments={})])
        )
        job_id = scheduled.job_id
        cad_batch_cancel(BatchCancelInput(job_id=job_id))
        result = cad_batch_cancel(BatchCancelInput(job_id=job_id))
        assert result.status == "error"
