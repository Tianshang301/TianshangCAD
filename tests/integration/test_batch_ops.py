"""Batch processing integration tests."""

from __future__ import annotations

import json

from cad_mcp_server.mcp.tools.batch import (
    BatchCommand,
    BatchExecuteInput,
    BatchScheduleInput,
    BatchStatusInput,
    cad_batch_execute,
    cad_batch_schedule,
    cad_batch_status,
)
from cad_mcp_server.mcp.tools.crud import FileCreateInput, cad_file_create
from cad_mcp_server.mcp.tools.json_ops import (
    JsonExportGeometryInput,
    JsonImportGeometryInput,
    cad_json_export_geometry,
    cad_json_import_geometry,
)


class TestBatchOperations:
    """Batch workflow covering the core Phase 2 loop."""

    def test_batch_import_measure_export(self) -> None:
        cad_file_create(FileCreateInput(filename="batch.json", unit="mm"))

        geometry = json.dumps(
            [
                {
                    "id": f"obj_{i}",
                    "type": "circle",
                    "layer": "0",
                    "geometry": {
                        "type": "circle",
                        "center": [i * 10, 0, 0],
                        "radius": 2,
                    },
                }
                for i in range(5)
            ]
        )

        result = cad_batch_execute(
            BatchExecuteInput(
                commands=[
                    BatchCommand(
                        tool="cad_json_import_geometry",
                        arguments={"json_data": geometry, "coordinate_system": "world"},
                    ),
                    BatchCommand(tool="cad_metrics_get", arguments={}),
                ]
            )
        )
        assert result.status == "success"
        assert result.success_count == 2

        metrics = result.results[1].result
        assert metrics["objects"] == 5
        assert metrics["kinds"]["circle"] == 5

        exported = cad_json_export_geometry(JsonExportGeometryInput())
        assert exported.count == 5

    def test_scheduled_then_executed(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(
                name="report",
                commands=[BatchCommand(tool="cad_metrics_get", arguments={})],
            )
        )
        job_id = scheduled.job_id
        status = cad_batch_status(BatchStatusInput(job_id=job_id))
        assert status.state == "pending"

        cad_file_create(FileCreateInput(filename="report.json"))
        cad_json_import_geometry(
            JsonImportGeometryInput(
                json_data=json.dumps(
                    {
                        "id": "l1",
                        "type": "line",
                        "layer": "0",
                        "geometry": {"type": "line", "start": [0, 0, 0], "end": [1, 1, 0]},
                    }
                )
            )
        )
        execute = cad_batch_execute(
            BatchExecuteInput(commands=[BatchCommand(tool="cad_metrics_get", arguments={})])
        )
        assert execute.success_count == 1
        assert execute.results[0].result["objects"] == 1
