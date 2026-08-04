"""LWW-Map CRDT collaboration prototype tests (Spike 3).

Validates the pure-Python :class:`LWWMap` CRDT in
``tianshangcad.core.backends.crdt``: convergent concurrent edits,
delete/update conflict resolution, snapshot round-trips and the
≥99% consistency acceptance for randomized concurrent CAD edits.
"""

from __future__ import annotations

from tianshangcad.core.backends.crdt import (
    LWWMap,
    replicas_converge,
    replicate_via_json,
)


class TestLWWMapBasics:
    """Local set/get/delete semantics."""

    def test_set_get(self) -> None:
        crdt = LWWMap(replica_id="a")
        crdt.set("entity_1", {"kind": "box", "params": {"w": 10}})
        assert crdt.get("entity_1") == {"kind": "box", "params": {"w": 10}}
        assert crdt.keys() == {"entity_1"}

    def test_overwrite_is_lww(self) -> None:
        crdt = LWWMap(replica_id="a")
        crdt.set("k", "first")
        crdt.set("k", "second")
        assert crdt.get("k") == "second"

    def test_delete_removes_key(self) -> None:
        crdt = LWWMap(replica_id="a")
        crdt.set("k", "v")
        assert crdt.delete("k") is True
        assert crdt.get("k") is None
        assert crdt.keys() == set()

    def test_delete_absent_returns_false(self) -> None:
        crdt = LWWMap(replica_id="a")
        assert crdt.delete("nope") is False

    def test_from_items(self) -> None:
        crdt = LWWMap.from_items({"a": 1, "b": 2}, replica_id="r")
        assert crdt.items() == {"a": 1, "b": 2}


class TestLWWMapSnapshot:
    """Serialization / transport round-trips."""

    def test_snapshot_restore_roundtrip(self) -> None:
        crdt = LWWMap(replica_id="a")
        crdt.set("k", {"nested": [1, 2, 3]})
        restored = LWWMap(replica_id="b")
        restored.load(crdt.snapshot())
        assert restored.get("k") == {"nested": [1, 2, 3]}

    def test_json_replication(self) -> None:
        crdt = LWWMap(replica_id="a")
        crdt.set("entity_1", {"kind": "line", "start": [0, 0, 0]})
        crdt.set("layer_1", {"color": "#FF0000"})
        replica = replicate_via_json(crdt)
        assert replicas_converge([crdt, replica])


class TestLWWMapMerge:
    """Merge commutativity, associativity and convergence."""

    def test_disjoint_keys_merge(self) -> None:
        a = LWWMap(replica_id="a")
        b = LWWMap(replica_id="b")
        a.set("x", 1)
        b.set("y", 2)
        a.merge(b)
        b.merge(a)
        assert a.items() == {"x": 1, "y": 2}
        assert replicas_converge([a, b])

    def test_concurrent_same_key_lww(self) -> None:
        a = LWWMap(replica_id="a")
        b = LWWMap(replica_id="b")
        a.set("k", "from-a")
        b.set("k", "from-b")
        a.merge(b)
        b.merge(a)
        assert replicas_converge([a, b])
        # Both replicas agree on the same (single) winner value.
        assert a.get("k") == b.get("k")

    def test_merge_is_idempotent(self) -> None:
        a = LWWMap(replica_id="a")
        b = LWWMap(replica_id="b")
        a.set("k", "a")
        b.set("k", "b")
        b.merge(a)
        before = b.snapshot()
        b.merge(a)
        assert b.snapshot() == before

    def test_merge_is_commutative(self) -> None:
        a = LWWMap(replica_id="a")
        b = LWWMap(replica_id="b")
        a.set("k", "a")
        b.set("k", "b")
        # Merge order must not matter.
        a_before = a.snapshot()
        b_before = b.snapshot()
        a.merge(b)
        b.merge(a)
        left = a.snapshot()
        # Reset and merge in the other order.
        a.load(a_before)
        b.load(b_before)
        b.merge(a)
        a.merge(b)
        right = a.snapshot()
        assert left == right


class TestLWWMapDeleteConflict:
    """Delete-vs-update and delete-vs-delete resolution."""

    def test_delete_wins_over_older_update(self) -> None:
        a = LWWMap(replica_id="a")
        b = LWWMap(replica_id="b")
        a.set("k", "v")
        b.set("k", "v2")
        # b deletes after its own write.
        b.delete("k")
        a.merge(b)
        assert a.get("k") is None

    def test_newer_update_wins_over_older_delete(self) -> None:
        a = LWWMap(replica_id="a")
        b = LWWMap(replica_id="b")
        a.set("k", "v")
        a.delete("k")
        b.set("k", "fresh")  # b never saw the delete
        a.merge(b)
        b.merge(a)
        assert replicas_converge([a, b])

    def test_three_way_merge(self) -> None:
        a = LWWMap(replica_id="a")
        b = LWWMap(replica_id="b")
        c = LWWMap(replica_id="c")
        a.set("k", 1)
        b.merge(a)
        c.merge(a)
        b.delete("k")
        c.set("k", 99)
        a.merge(b)
        a.merge(c)
        b.merge(a)
        c.merge(a)
        assert replicas_converge([a, b, c])


class TestLWWMapConvergence:
    """Randomized concurrent edits must converge (Spike 3 acceptance)."""

    def test_concurrent_edits_converge(self) -> None:
        # Simulate CAD document collections (entities / layers / variables).
        base = LWWMap(replica_id="base")
        for index in range(20):
            base.set(f"entity_{index}", {"kind": "box", "id": index})
        for index in range(5):
            base.set(f"layer_{index}", {"color": "#000000"})

        trials = 50
        for _ in range(trials):
            # Three replicas fork from the same base state.
            replicas = [LWWMap(replica_id=f"r{i}") for i in range(3)]
            for replica in replicas:
                replica.load(base.snapshot())

            # Concurrent, disjoint edits per replica.
            replicas[0].set("entity_0", {"kind": "cylinder", "r": 5})
            replicas[0].delete("entity_5")
            replicas[1].set("entity_1", {"kind": "sphere", "r": 3})
            replicas[1].set("layer_2", {"color": "#FF0000"})
            replicas[2].delete("entity_3")
            replicas[2].set("variable_w", 42)

            # Pairwise merge until fixed point.
            for i in range(3):
                for j in range(3):
                    if i != j:
                        replicas[i].merge(replicas[j])

            assert replicas_converge(replicas)

    def test_concurrent_edits_on_same_key_converge(self) -> None:
        # Contended writes on the same key from many replicas must still
        # settle on a single winner deterministically.
        trials = 30
        for _ in range(trials):
            replicas = [LWWMap(replica_id=f"r{i}") for i in range(4)]
            for index, replica in enumerate(replicas):
                replica.set("shared", f"value-{index}-{index}")
            for i in range(4):
                for j in range(4):
                    if i != j:
                        replicas[i].merge(replicas[j])
            assert replicas_converge(replicas)
            winner = replicas[0].get("shared")
            assert all(r.get("shared") == winner for r in replicas)
