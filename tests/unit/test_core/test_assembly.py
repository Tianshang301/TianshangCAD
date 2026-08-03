"""Assembly modelling unit tests."""

from __future__ import annotations

import pytest

from cad_mcp_server.core.assembly import (
    AssemblyDocument,
    AssemblyNode,
    Mate,
    MateType,
    identity_transform,
)
from cad_mcp_server.utils.errors import AssemblyError


def _part(
    doc: AssemblyDocument,
    name: str,
    translation: list[float] | None = None,
    parent_id: str | None = None,
) -> str:
    local = (
        {"translation": translation, "euler": [0.0, 0.0, 0.0]}
        if translation is not None
        else None
    )
    return doc.add_part(name=name, local=local, parent_id=parent_id)


class TestAssemblyTree:
    """Tree building and node management."""

    def test_add_part_root(self) -> None:
        doc = AssemblyDocument("asm")
        node_id = _part(doc, "shaft")
        node = doc.get_node(node_id)
        assert node.kind == "part"
        assert node.is_part
        assert len(doc.nodes) == 1

    def test_add_part_under_subassembly(self) -> None:
        doc = AssemblyDocument()
        sub = doc.add_subassembly("motor")
        part = _part(doc, "rotor", parent_id=sub)
        assert doc._children[sub] == [part]

    def test_add_mate_validates_nodes(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a")
        with pytest.raises(AssemblyError):
            doc.add_mate("coincident", a, "missing")

    def test_add_mate_same_node(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a")
        with pytest.raises(AssemblyError):
            doc.add_mate("coincident", a, a)

    def test_add_mate_invalid_type(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a")
        b = _part(doc, "b")
        with pytest.raises(AssemblyError):
            doc.add_mate("weld", a, b)

    def test_remove_node_cascades(self) -> None:
        doc = AssemblyDocument()
        sub = doc.add_subassembly("sub")
        part = _part(doc, "p", parent_id=sub)
        doc.add_mate("coincident", sub, part)
        doc.remove_node(sub)
        with pytest.raises(AssemblyError):
            doc.get_node(part)
        assert len(doc.mates) == 0

    def test_remove_node_missing(self) -> None:
        with pytest.raises(AssemblyError):
            AssemblyDocument().remove_node("nope")

    def test_remove_mate(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a")
        b = _part(doc, "b")
        mate_id = doc.add_mate("distance", a, b, {"distance": 5.0})
        doc.remove_mate(mate_id)
        assert len(doc.mates) == 0
        with pytest.raises(AssemblyError):
            doc.get_mate(mate_id)


class TestMateTypes:
    """Mate type construction and defaults."""

    def test_mate_type_enum_values(self) -> None:
        values = [m.value for m in MateType]
        assert values == [
            "coincident",
            "concentric",
            "parallel",
            "perpendicular",
            "distance",
            "angle",
        ]

    def test_mate_accepts_lowercase_string(self) -> None:
        mate = Mate("CONCENTRIC", "a", "b")
        assert mate.type == MateType.CONCENTRIC

    def test_mate_invalid_type_raises(self) -> None:
        with pytest.raises(AssemblyError):
            Mate("bad", "a", "b")

    def test_mate_requires_two_nodes(self) -> None:
        with pytest.raises(AssemblyError):
            Mate("coincident", "", "b")


class TestSolve:
    """Mate solving produces exact transforms."""

    def test_distance_mate_offsets_along_axis(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a")
        b = _part(doc, "b")
        doc.add_mate("distance", a, b, {"distance": 25.0, "axis": [1, 0, 0]})
        world = doc.solve()
        assert world[b]["translation"] == [25.0, 0.0, 0.0]

    def test_coincident_mate_aligns_origins(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a", translation=[10.0, 20.0, 0.0])
        b = _part(doc, "b", translation=[0.0, 0.0, 0.0])
        doc.add_mate("coincident", a, b)
        world = doc.solve()
        assert world[b]["translation"] == [10.0, 20.0, 0.0]

    def test_concentric_mate_aligns_centers(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a", translation=[5.0, 5.0, 0.0])
        b = _part(doc, "b")
        doc.add_mate("concentric", a, b)
        world = doc.solve()
        assert world[b]["translation"] == [5.0, 5.0, 0.0]

    def test_parallel_mate_preserves_position(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a", translation=[3.0, 4.0, 0.0])
        b = _part(doc, "b", translation=[1.0, 1.0, 0.0])
        doc.add_mate("parallel", a, b)
        world = doc.solve()
        assert world[b]["translation"] == [1.0, 1.0, 0.0]

    def test_perpendicular_mate_rotates_ninety(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a")
        b = _part(doc, "b")
        doc.add_mate("perpendicular", a, b)
        world = doc.solve()
        import math

        assert abs(world[b]["euler"][0] - math.pi / 2.0) < 1e-9

    def test_angle_mate_rotates_by_angle(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a")
        b = _part(doc, "b")
        doc.add_mate("angle", a, b, {"angle": 90.0})
        world = doc.solve()
        import math

        assert abs(world[b]["euler"][0] - math.pi / 2.0) < 1e-9

    def test_closed_loop_chain(self) -> None:
        """A multi-mate chain solves exactly end to end."""
        doc = AssemblyDocument()
        base = _part(doc, "base")
        mid = _part(doc, "mid")
        top = _part(doc, "top")
        doc.add_mate("distance", base, mid, {"distance": 10.0, "axis": [1, 0, 0]})
        doc.add_mate("distance", mid, top, {"distance": 20.0, "axis": [0, 1, 0]})
        world = doc.solve()
        assert world[base]["translation"] == [0.0, 0.0, 0.0]
        assert world[mid]["translation"] == [10.0, 0.0, 0.0]
        # top is offset 20 along y from mid's world position.
        assert world[top]["translation"] == [10.0, 20.0, 0.0]

    def test_solve_with_no_mates_returns_identity(self) -> None:
        doc = AssemblyDocument()
        a = _part(doc, "a")
        world = doc.solve()
        assert world[a]["translation"] == [0.0, 0.0, 0.0]

    def test_subassembly_composition(self) -> None:
        doc = AssemblyDocument()
        sub = doc.add_subassembly("motor")
        part = _part(doc, "rotor", translation=[5.0, 0.0, 0.0], parent_id=sub)
        world = doc.solve()
        # Root sub-assembly contributes identity; part sits at its local offset.
        assert world[part]["translation"] == [5.0, 0.0, 0.0]
        assert world[sub]["translation"] == [0.0, 0.0, 0.0]


class TestBom:
    """Bill of materials statistics."""

    def test_bom_tallies_duplicates(self) -> None:
        doc = AssemblyDocument()
        _part(doc, "bolt")
        _part(doc, "bolt")
        _part(doc, "nut")
        rows = doc.bom()
        by_name = {row["name"]: row for row in rows}
        assert by_name["bolt"]["quantity"] == 2
        assert by_name["nut"]["quantity"] == 1

    def test_bom_expands_subassemblies(self) -> None:
        doc = AssemblyDocument()
        sub = doc.add_subassembly("motor")
        _part(doc, "rotor", parent_id=sub)
        _part(doc, "stator", parent_id=sub)
        rows = doc.bom()
        assert {row["name"] for row in rows} == {"rotor", "stator"}

    def test_bom_empty(self) -> None:
        assert AssemblyDocument().bom() == []

    def test_bom_csv(self) -> None:
        doc = AssemblyDocument()
        _part(doc, "bolt")
        _part(doc, "bolt")
        csv_text = doc.bom_csv()
        assert csv_text.startswith("name,quantity,entity_id")
        assert "bolt,2" in csv_text

    def test_bom_retains_entity_id(self) -> None:
        doc = AssemblyDocument()
        node_id = doc.add_part("gear", entity_id="ent_1")
        rows = doc.bom()
        assert rows[0]["entity_id"] == "ent_1"
        assert node_id  # node created


class TestExplode:
    """Exploded view offset correctness."""

    def test_explode_offsets_by_depth(self) -> None:
        doc = AssemblyDocument()
        sub = doc.add_subassembly("sub")
        part = _part(doc, "p", parent_id=sub)
        records = doc.explode(spacing=5.0, direction="z")
        by_id = {record["node_id"]: record for record in records}
        assert by_id[sub]["depth"] == 1
        assert by_id[part]["depth"] == 2
        assert by_id[sub]["translation"][2] == 5.0
        assert by_id[part]["translation"][2] == 10.0

    def test_explode_direction_axes(self) -> None:
        doc = AssemblyDocument()
        _part(doc, "a")
        x = doc.explode(spacing=7.0, direction="x")
        assert x[0]["translation"][0] == 7.0
        y = doc.explode(spacing=7.0, direction="y")
        assert y[0]["translation"][1] == 7.0
        z = doc.explode(spacing=7.0, direction="z")
        assert z[0]["translation"][2] == 7.0

    def test_explode_empty(self) -> None:
        assert AssemblyDocument().explode() == []


class TestSerialization:
    """to_dict/from_dict round-trips."""

    def test_roundtrip_full(self) -> None:
        doc = AssemblyDocument("engine")
        sub = doc.add_subassembly("motor")
        part = _part(doc, "rotor", parent_id=sub)
        doc.add_mate("distance", sub, part, {"distance": 3.0, "axis": [0, 1, 0]})
        restored = AssemblyDocument.from_dict(doc.to_dict())
        assert restored.name == "engine"
        assert len(restored.nodes) == 2
        assert len(restored.mates) == 1
        world = restored.solve()
        assert world[part]["translation"] == [0.0, 3.0, 0.0]

    def test_node_roundtrip(self) -> None:
        node = AssemblyNode("pt_1", "shaft", "part", {"translation": [1, 2, 3], "euler": [0, 0, 0]})
        restored = AssemblyNode.from_dict(node.to_dict())
        assert restored.name == "shaft"
        assert restored.local["translation"] == [1, 2, 3]

    def test_mate_roundtrip(self) -> None:
        mate = Mate("angle", "a", "b", {"angle": 45.0})
        restored = Mate.from_dict(mate.to_dict())
        assert restored.type == MateType.ANGLE
        assert restored.params["angle"] == 45.0

    def test_identity_transform_is_fresh(self) -> None:
        a = identity_transform()
        b = identity_transform()
        assert a is not b
        assert a == {"translation": [0.0, 0.0, 0.0], "euler": [0.0, 0.0, 0.0]}
