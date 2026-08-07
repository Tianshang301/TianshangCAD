"""MCP assembly tool tests."""

from __future__ import annotations

from tianshangcad.mcp.tools.assembly import (
    AssemblyAddMateInput,
    AssemblyAddPartInput,
    AssemblyAddSubasmInput,
    AssemblyBomInput,
    AssemblyCreateInput,
    AssemblyExplodeInput,
    AssemblyRemovePartInput,
    AssemblySolveInput,
    cad_assembly_add_mate,
    cad_assembly_add_part,
    cad_assembly_add_subasm,
    cad_assembly_bom,
    cad_assembly_create,
    cad_assembly_explode,
    cad_assembly_remove_part,
    cad_assembly_solve,
)
from tianshangcad.mcp.tools.crud import FileCreateInput, cad_file_create


class TestAssemblyTools:
    """`cad_assembly_*` tool tests."""

    def _setup(self) -> tuple[str, str]:
        cad_file_create(FileCreateInput(filename="assembly.json"))
        cad_assembly_create(AssemblyCreateInput(name="engine"))
        node_a = cad_assembly_add_part(
            AssemblyAddPartInput(name="base", translation=[0, 0, 0])
        ).node_id
        node_b = cad_assembly_add_part(
            AssemblyAddPartInput(name="gear", translation=[0, 0, 0])
        ).node_id
        return node_a, node_b

    def test_create(self) -> None:
        cad_file_create(FileCreateInput(filename="a.json"))
        result = cad_assembly_create(AssemblyCreateInput(name="engine"))
        assert result.status == "success"
        assert result.name == "engine"

    def test_create_no_document(self) -> None:
        from tianshangcad.core.session import SessionManager

        SessionManager().reset()
        result = cad_assembly_create(AssemblyCreateInput(name="engine"))
        assert result.status == "error"

    def test_add_part(self) -> None:
        node_a, _ = self._setup()
        result = cad_assembly_add_part(
            AssemblyAddPartInput(name="sprocket", parent_id=node_a)
        )
        assert result.status == "success"
        assert result.node_id != ""

    def test_add_part_invalid_parent(self) -> None:
        self._setup()
        result = cad_assembly_add_part(
            AssemblyAddPartInput(name="p", parent_id="nope")
        )
        assert result.status == "error"

    def test_add_subasm(self) -> None:
        self._setup()
        result = cad_assembly_add_subasm(AssemblyAddSubasmInput(name="motor"))
        assert result.status == "success"
        assert result.node_id != ""

    def test_add_mate(self) -> None:
        node_a, node_b = self._setup()
        result = cad_assembly_add_mate(
            AssemblyAddMateInput(
                mate_type="distance", node_a=node_a, node_b=node_b,
                distance=15.0, axis=[1, 0, 0],
            )
        )
        assert result.status == "success"
        assert result.mate_id != ""

    def test_add_mate_invalid_type(self) -> None:
        node_a, node_b = self._setup()
        result = cad_assembly_add_mate(
            AssemblyAddMateInput(mate_type="weld", node_a=node_a, node_b=node_b)
        )
        assert result.status == "error"

    def test_solve(self) -> None:
        node_a, node_b = self._setup()
        cad_assembly_add_mate(
            AssemblyAddMateInput(
                mate_type="distance", node_a=node_a, node_b=node_b,
                distance=25.0, axis=[1, 0, 0],
            )
        )
        result = cad_assembly_solve(AssemblySolveInput())
        assert result.status == "success"
        assert result.transforms[node_b]["translation"] == [25.0, 0.0, 0.0]
        assert result.mate_count == 1

    def test_bom(self) -> None:
        self._setup()
        cad_assembly_add_part(AssemblyAddPartInput(name="gear"))
        result = cad_assembly_bom(AssemblyBomInput())
        assert result.status == "success"
        assert result.part_count == 3

    def test_bom_csv(self) -> None:
        self._setup()
        result = cad_assembly_bom(AssemblyBomInput(format="csv"))
        assert result.status == "success"
        assert result.csv is not None
        assert result.csv.startswith("name,quantity,entity_id")

    def test_explode(self) -> None:
        self._setup()
        result = cad_assembly_explode(AssemblyExplodeInput(spacing=5.0, direction="z"))
        assert result.status == "success"
        assert len(result.records) == 2
        assert result.records[0]["translation"][2] == 5.0

    def test_remove_part(self) -> None:
        _, node_b = self._setup()
        result = cad_assembly_remove_part(AssemblyRemovePartInput(node_id=node_b))
        assert result.status == "success"
        bom = cad_assembly_bom(AssemblyBomInput())
        assert bom.part_count == 1

    def test_remove_part_unknown(self) -> None:
        self._setup()
        result = cad_assembly_remove_part(AssemblyRemovePartInput(node_id="nope"))
        assert result.status == "error"
