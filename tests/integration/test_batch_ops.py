"""Batch processing integration tests."""

from __future__ import annotations

import json
import time

from tianshangcad.mcp.tools.batch import (
    BatchCommand,
    BatchExecuteInput,
    BatchScheduleInput,
    BatchStatusInput,
    cad_batch_execute,
    cad_batch_schedule,
    cad_batch_status,
)
from tianshangcad.mcp.tools.crud import FileCreateParams, FileInput, cad_file
from tianshangcad.mcp.tools.json_ops import (
    JsonExportGeometryParams,
    JsonInput,
    cad_json,
)


def _wait_for(job_id: str, states: set[str], timeout: float = 5.0) -> str:
    """Poll ``cad_batch_status`` until ``job_id`` reaches one of ``states``."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = cad_batch_status(BatchStatusInput(job_id=job_id))
        if status.state in states:
            return status.state
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} did not reach {states}; got {status.state}")


class TestBatchOperations:
    """Batch workflow covering the core Phase 2 loop."""

    def test_batch_import_measure_export(self) -> None:
        cad_file(FileInput(file=FileCreateParams(filename="batch.json", unit="mm")))

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
                        tool="cad_json",
                        arguments={
                            "params": {
                                "action": "import_geometry",
                                "json_data": geometry,
                                "coordinate_system": "world",
                            }
                        },
                    ),
                    BatchCommand(
                        tool="cad_validate",
                        arguments={"query": {"action": "metrics"}},
                    ),
                ]
            )
        )
        assert result.status == "success"
        assert result.success_count == 2

        metrics = result.results[1].result
        assert metrics["objects"] == 5
        assert metrics["kinds"]["circle"] == 5

        exported = cad_json(JsonInput(params=JsonExportGeometryParams()))
        assert exported.object_count == 5

    def test_scheduled_then_executed(self) -> None:
        scheduled = cad_batch_schedule(
            BatchScheduleInput(
                name="report",
                commands=[
                    BatchCommand(
                        tool="cad_validate",
                        arguments={"query": {"action": "metrics"}},
                    )
                ],
            )
        )
        job_id = scheduled.job_id
        state = _wait_for(job_id, {"done", "error"})
        assert state == "done"

        status = cad_batch_status(BatchStatusInput(job_id=job_id))
        assert status.results is not None
        assert status.results[0].success is True
