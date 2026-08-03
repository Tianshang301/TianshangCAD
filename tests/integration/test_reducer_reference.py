"""Single-stage reducer reference workflow (gear + shaft + housing).

Phase 7 Task C reference example: build a reducer assembly, solve its
mates, generate a BOM, create an engineering drawing and export it. This is
the canonical end-to-end walk-through of the Phase 7 A + B tooling.
"""

from __future__ import annotations

import json
import os

from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.mcp.tools.assembly import (
    AssemblyAddMateInput,
    AssemblyAddPartInput,
    AssemblyBomInput,
    AssemblyCreateInput,
    AssemblySolveInput,
    cad_assembly_add_mate,
    cad_assembly_add_part,
    cad_assembly_bom,
    cad_assembly_create,
    cad_assembly_solve,
)
from cad_mcp_server.mcp.tools.drawing import (
    DrawingAddDimensionInput,
    DrawingAddToleranceInput,
    DrawingAddViewInput,
    DrawingCreateInput,
    DrawingExportInput,
    cad_drawing_add_dimension,
    cad_drawing_add_tolerance,
    cad_drawing_add_view,
    cad_drawing_create,
    cad_drawing_export,
)


def _build_reducer() -> DocumentManager:
    """Create a document and populate a single-stage reducer assembly."""
    manager = DocumentManager()
    manager.create("reducer.json", unit="mm")
    doc = manager.get_current()
    assembly = doc.assembly("reducer")

    housing = assembly.add_part("housing", properties={"material": "cast_iron"})
    input_shaft = assembly.add_part(
        "input_shaft",
        local={"translation": [40.0, 0.0, 20.0], "euler": [0.0, 0.0, 0.0]},
        properties={"material": "steel"},
    )
    gear = assembly.add_part(
        "gear",
        local={"translation": [40.0, 0.0, 20.0], "euler": [0.0, 0.0, 0.0]},
        properties={"material": "steel", "teeth": 38},
    )
    output_shaft = assembly.add_part(
        "output_shaft",
        local={"translation": [90.0, 0.0, 20.0], "euler": [0.0, 0.0, 0.0]},
        properties={"material": "steel"},
    )
    cover = assembly.add_part(
        "cover",
        local={"translation": [0.0, 0.0, 60.0], "euler": [0.0, 0.0, 0.0]},
        properties={"material": "cast_iron"},
    )

    assembly.add_mate("coincident", housing, cover)
    assembly.add_mate("concentric", input_shaft, gear, {"axis": [0.0, 0.0, 1.0]})
    assembly.add_mate("distance", input_shaft, output_shaft, {"distance": 50.0})
    assembly.add_mate("parallel", housing, output_shaft)
    return manager


class TestReducerReference:
    """End-to-end single-stage reducer example."""

    def test_assembly_solve_and_bom(self) -> None:
        manager = _build_reducer()
        doc = manager.get_current()

        assert cad_assembly_create(AssemblyCreateInput(name="reducer")).status == "success"

        bracket = cad_assembly_add_part(
            AssemblyAddPartInput(
                name="bracket",
                translation=[0.0, 0.0, 80.0],
                properties={"material": "steel"},
            )
        )
        assert bracket.status == "success"
        assert bracket.node_id

        cover_id = next(
            node.id for node in doc._assembly.nodes if node.name == "cover"
        )
        mate = cad_assembly_add_mate(
            AssemblyAddMateInput(
                mate_type="coincident",
                node_a=cover_id,
                node_b=bracket.node_id,
            )
        )
        assert mate.status == "success"

        solved = cad_assembly_solve(AssemblySolveInput())
        assert solved.status == "success"
        assert solved.mate_count == 5
        assert len(solved.transforms) == 6

        bom = cad_assembly_bom(AssemblyBomInput(format="json"))
        assert bom.status == "success"
        assert bom.part_count == 6
        names = {row["name"] for row in bom.bom}
        assert names == {
            "housing",
            "input_shaft",
            "gear",
            "output_shaft",
            "cover",
            "bracket",
        }

    def test_drawing_and_export(self, tmp_path) -> None:
        _build_reducer()

        created = cad_drawing_create(
            DrawingCreateInput(
                name="reducer_drawing",
                paper="A3",
                title="Single-stage reducer - general arrangement",
            )
        )
        assert created.status == "success"

        view = cad_drawing_add_view(
            DrawingAddViewInput(
                name="main",
                view_type="main",
                scale=0.5,
                translation=[80.0, 120.0],
            )
        )
        assert view.status == "success"

        dimension = cad_drawing_add_dimension(
            DrawingAddDimensionInput(
                dim_type="linear",
                value=180.0,
                points=[[0.0, 0.0], [180.0, 0.0]],
                position=[90.0, -20.0],
            )
        )
        assert dimension.status == "success"

        tolerance = cad_drawing_add_tolerance(
            DrawingAddToleranceInput(
                symbol="position",
                value=0.05,
                datum="A",
            )
        )
        assert tolerance.status == "success"

        output = tmp_path / "reducer.svg"
        exported = cad_drawing_export(
            DrawingExportInput(format="svg", path=str(output))
        )
        assert exported.status == "success"
        assert output.exists()
        assert output.stat().st_size > 0

    def test_reference_json_artifacts(self, tmp_path) -> None:
        """Emit the reference JSON artifacts (assembly, drawing, BOM)."""
        manager = _build_reducer()
        doc = manager.get_current()

        cad_assembly_solve(AssemblySolveInput())
        bom = cad_assembly_bom(AssemblyBomInput(format="json"))

        cad_drawing_create(
            DrawingCreateInput(name="reducer_drawing", paper="A3")
        )
        cad_drawing_add_view(
            DrawingAddViewInput(name="main", view_type="main", scale=0.5)
        )

        reference = {
            "name": "single_stage_reducer",
            "description": (
                "Phase 7 Task C reference: gear + shaft + housing reducer. "
                "Assembly, drawing and BOM produced end-to-end by the MCP tools."
            ),
            "assembly": doc._assembly.to_dict() if doc._assembly else None,
            "drawing": doc._drawing.to_dict() if doc._drawing else None,
            "bom": bom.bom,
        }

        path = tmp_path / "reducer_reference.json"
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(reference, handle, indent=2)

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["name"] == "single_stage_reducer"
        assert len(data["assembly"]["nodes"]) == 5
        assert len(data["assembly"]["mates"]) == 4
        assert len(data["bom"]) == 5
        assert data["drawing"]["paper"] == "A3"
        assert path.stat().st_size > 0
        assert os.path.getsize(path) > 0
