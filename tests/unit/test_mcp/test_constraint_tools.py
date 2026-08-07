"""MCP constraint tool tests."""

from __future__ import annotations

from tianshangcad.mcp.tools.constraint import (
    ConstraintAddInput,
    ConstraintAddParams,
    ConstraintInput,
    ConstraintListInput,
    ConstraintListParams,
    ConstraintRemoveInput,
    ConstraintRemoveParams,
    ConstraintSolveInput,
    ConstraintSolveParams,
    cad_constraint,
    cad_constraint_add,
    cad_constraint_list,
    cad_constraint_remove,
    cad_constraint_solve,
)
from tianshangcad.mcp.tools.crud import (
    ObjectCreateInput,
    cad_file_create,
    cad_object_create,
)


class TestConstraintTools:
    """`cad_constraint_*` tool tests."""

    def _setup(self) -> tuple[str, str]:
        from tianshangcad.mcp.tools.crud import FileCreateInput

        cad_file_create(FileCreateInput(filename="constraint.json"))
        line_a = cad_object_create(
            ObjectCreateInput(
                type="line", params={"start": [0, 0, 0], "end": [10, 0, 0]}, layer="0"
            )
        ).object_id
        line_b = cad_object_create(
            ObjectCreateInput(
                type="line", params={"start": [0, 5, 0], "end": [8, 5, 0]}, layer="0"
            )
        ).object_id
        return line_a, line_b

    def test_add_parallel(self) -> None:
        line_a, line_b = self._setup()
        result = cad_constraint_add(
            ConstraintAddInput(type="parallel", entities=[line_a, line_b])
        )
        assert result.status == "success"
        assert result.constraint_id != ""

    def test_add_invalid_type(self) -> None:
        line_a, line_b = self._setup()
        result = cad_constraint_add(
            ConstraintAddInput(type="bogus", entities=[line_a, line_b])
        )
        assert result.status == "error"

    def test_add_missing_entity(self) -> None:
        line_a, _ = self._setup()
        result = cad_constraint_add(
            ConstraintAddInput(type="parallel", entities=[line_a, "nope"])
        )
        # entity existence is validated at solve time, not add time
        assert result.status == "success"

    def test_list_empty(self) -> None:
        from tianshangcad.mcp.tools.crud import FileCreateInput

        cad_file_create(FileCreateInput(filename="constraint2.json"))
        result = cad_constraint_list(ConstraintListInput())
        assert result.status == "success"
        assert result.count == 0

    def test_remove(self) -> None:
        line_a, line_b = self._setup()
        added = cad_constraint_add(
            ConstraintAddInput(type="parallel", entities=[line_a, line_b])
        )
        result = cad_constraint_remove(ConstraintRemoveInput(constraint_id=added.constraint_id))
        assert result.status == "success"
        listed = cad_constraint_list(ConstraintListInput())
        assert listed.count == 0

    def test_remove_missing(self) -> None:
        self._setup()
        result = cad_constraint_remove(ConstraintRemoveInput(constraint_id="nope"))
        assert result.status == "error"

    def test_solve_no_document(self) -> None:
        from tianshangcad.mcp.tools.status import SessionManager

        SessionManager().reset()
        result = cad_constraint_solve(ConstraintSolveInput())
        assert result.status == "error"
        assert "No active document" in result.message

    def test_solve_no_constraints(self) -> None:
        self._setup()
        result = cad_constraint_solve(ConstraintSolveInput())
        assert result.status == "success"
        assert result.converged

    def test_solve_parallel(self) -> None:
        line_a, line_b = self._setup()
        cad_constraint_add(ConstraintAddInput(type="fixed", entities=[line_a]))
        cad_constraint_add(ConstraintAddInput(type="parallel", entities=[line_a, line_b]))
        result = cad_constraint_solve(ConstraintSolveInput())
        assert result.status == "success"
        assert result.converged
        assert line_b in result.moved_entities

    def test_solve_persists_roundtrip(self) -> None:
        from tianshangcad.core.session import SessionManager

        line_a, line_b = self._setup()
        cad_constraint_add(ConstraintAddInput(type="parallel", entities=[line_a, line_b]))
        doc = SessionManager().current_session.current_file_id
        from tianshangcad.core.document import DocumentManager

        data = DocumentManager()._require(doc).to_dict()
        assert len(data["constraints"]) == 1


class TestConstraintAggregate:
    """Aggregate cad_constraint tool (discriminated action)."""

    def _setup(self) -> tuple[str, str]:
        from tianshangcad.mcp.tools.crud import FileCreateInput

        cad_file_create(FileCreateInput(filename="constraint.json"))
        line_a = cad_object_create(
            ObjectCreateInput(type="line", params={"start": [0, 0, 0], "end": [10, 0, 0]})
        ).object_id
        line_b = cad_object_create(
            ObjectCreateInput(type="line", params={"start": [0, 5, 0], "end": [10, 5, 0]})
        ).object_id
        return line_a, line_b

    def test_action_add_success_and_error(self) -> None:
        line_a, _ = self._setup()
        ok = cad_constraint(
            ConstraintInput(
                constraint=ConstraintAddParams(
                    type="fixed", entities=[line_a]
                )
            )
        )
        assert ok.status == "success"
        assert ok.action == "add"
        assert ok.constraint_id != ""
        bad = cad_constraint(
            ConstraintInput(
                constraint=ConstraintAddParams(type="nope", entities=[line_a])
            )
        )
        assert bad.status == "error"

    def test_action_remove_success_and_missing(self) -> None:
        line_a, _ = self._setup()
        added = cad_constraint(
            ConstraintInput(constraint=ConstraintAddParams(type="fixed", entities=[line_a]))
        )
        ok = cad_constraint(
            ConstraintInput(
                constraint=ConstraintRemoveParams(constraint_id=added.constraint_id)
            )
        )
        assert ok.status == "success"
        missing = cad_constraint(
            ConstraintInput(constraint=ConstraintRemoveParams(constraint_id="nope"))
        )
        assert missing.status == "error"

    def test_action_list_and_count(self) -> None:
        line_a, line_b = self._setup()
        cad_constraint(
            ConstraintInput(
                constraint=ConstraintAddParams(type="parallel", entities=[line_a, line_b])
            )
        )
        listed = cad_constraint(ConstraintInput(constraint=ConstraintListParams()))
        assert listed.status == "success"
        assert listed.count == 1

    def test_action_solve_no_constraints_and_parallel(self) -> None:
        line_a, line_b = self._setup()
        empty = cad_constraint(ConstraintInput(constraint=ConstraintSolveParams()))
        assert empty.status == "success"
        assert empty.converged
        cad_constraint(
            ConstraintInput(constraint=ConstraintAddParams(type="fixed", entities=[line_a]))
        )
        cad_constraint(
            ConstraintInput(
                constraint=ConstraintAddParams(type="parallel", entities=[line_a, line_b])
            )
        )
        solved = cad_constraint(ConstraintInput(constraint=ConstraintSolveParams()))
        assert solved.status == "success"
        assert solved.converged
        assert line_b in solved.moved_entities
