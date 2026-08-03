"""Core collaboration tests: sessions, RBAC, branches, conflicts, presence."""

from __future__ import annotations

import pytest

from cad_mcp_server.core.collab import (
    CollabAction,
    CollabManager,
    CollaborationRole,
    CollabSession,
    ResourceScope,
    build_seed,
    can_act,
)
from cad_mcp_server.core.document import DocumentManager
from cad_mcp_server.utils.errors import DocumentError


def _assert_code(excinfo: pytest.ExceptionInfo[DocumentError], code: str) -> None:
    assert excinfo.value.code == code


class TestPermissionMatrix:
    """RBAC 4-role x 4-scope matrix."""

    @pytest.mark.parametrize(
        ("role", "scope", "action", "expected"),
        [
            (CollaborationRole.VIEWER, ResourceScope.DOCUMENT, CollabAction.READ, True),
            (CollaborationRole.VIEWER, ResourceScope.DOCUMENT, CollabAction.WRITE, False),
            (CollaborationRole.EDITOR, ResourceScope.DOCUMENT, CollabAction.WRITE, True),
            (CollaborationRole.EDITOR, ResourceScope.DOCUMENT, CollabAction.MANAGE, False),
            (CollaborationRole.ADMIN, ResourceScope.DOCUMENT, CollabAction.MANAGE, True),
            (CollaborationRole.ADMIN, ResourceScope.DOCUMENT, CollabAction.DELETE, False),
            (CollaborationRole.OWNER, ResourceScope.DOCUMENT, CollabAction.DELETE, True),
            (CollaborationRole.VIEWER, ResourceScope.SCENE, CollabAction.READ, True),
            (CollaborationRole.EDITOR, ResourceScope.SCENE, CollabAction.WRITE, True),
            (CollaborationRole.EDITOR, ResourceScope.SETTINGS, CollabAction.WRITE, False),
            (CollaborationRole.ADMIN, ResourceScope.SETTINGS, CollabAction.WRITE, True),
            (CollaborationRole.ADMIN, ResourceScope.SETTINGS, CollabAction.MANAGE, False),
            (CollaborationRole.OWNER, ResourceScope.SETTINGS, CollabAction.MANAGE, True),
            (CollaborationRole.VIEWER, ResourceScope.ASSEMBLY, CollabAction.READ, True),
            (CollaborationRole.EDITOR, ResourceScope.ASSEMBLY, CollabAction.WRITE, True),
            (CollaborationRole.OWNER, ResourceScope.ASSEMBLY, CollabAction.DELETE, True),
        ],
    )
    def test_can_act(self, role, scope, action, expected) -> None:
        assert can_act(role, scope, action) is expected

    def test_unknown_role_resolution(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        with pytest.raises(DocumentError) as exc:
            session.add_member("alice", "superuser")
        _assert_code(exc, "invalid_role")


class TestSessionLifecycle:
    """Session creation, membership and presence."""

    def test_create_and_role_of(self) -> None:
        session = CollabSession("s1", "d1", "design", "owner")
        assert session.role_of("owner") == CollaborationRole.OWNER
        with pytest.raises(DocumentError) as exc:
            session.role_of("bob")
        _assert_code(exc, "not_a_member")

    def test_manager_create_and_list(self) -> None:
        manager = CollabManager()
        session = manager.create_session("d1", name="review", owner="alice")
        assert manager.get_session(session.session_id) is session
        assert manager.list_sessions()[0]["owner"] == "alice"

    def test_get_session_missing(self) -> None:
        with pytest.raises(DocumentError) as exc:
            CollabManager().get_session("nope")
        _assert_code(exc, "session_not_found")

    def test_join_session_adds_viewer(self) -> None:
        manager = CollabManager()
        session = manager.create_session("d1", owner="alice")
        joined = manager.join_session(session.session_id, "bob")
        assert joined.role_of("bob") == CollaborationRole.VIEWER
        assert joined.presence["bob"]["status"] == "online"

    def test_close_session_owner_only(self) -> None:
        manager = CollabManager()
        session = manager.create_session("d1", owner="alice")
        manager.join_session(session.session_id, "bob")
        with pytest.raises(DocumentError) as exc:
            manager.close_session(session.session_id, "bob")
        _assert_code(exc, "permission_denied")
        manager.close_session(session.session_id, "alice")
        with pytest.raises(DocumentError) as exc:
            manager.get_session(session.session_id)
        _assert_code(exc, "session_not_found")

    def test_set_role_and_presence(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        session.add_member("alice", "editor")
        session.set_presence("alice", status="busy", cursor={"x": 1})
        assert session.presence["alice"]["status"] == "busy"
        assert session.presence["alice"]["cursor"] == {"x": 1}
        assert session.member_count() == 2


class TestOperations:
    """CRDT register writes and history."""

    def test_apply_op_writes_register(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        record = session.apply_op("owner", {"key": "entity:e1", "value": {"kind": "line"}})
        assert record["seq"] == 1
        assert session.state_dict()["entity:e1"] == {"kind": "line"}

    def test_apply_op_delete(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        session.apply_op("owner", {"key": "layer:0", "value": {"name": "0"}})
        session.apply_op("owner", {"key": "layer:0", "delete": True})
        assert "layer:0" not in session.state_dict()

    def test_apply_op_requires_write(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        session.add_member("bob", "viewer")
        with pytest.raises(DocumentError) as exc:
            session.apply_op("bob", {"key": "k", "value": 1})
        _assert_code(exc, "permission_denied")

    def test_apply_op_invalid(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        with pytest.raises(DocumentError) as exc:
            session.apply_op("owner", {"value": 1})
        _assert_code(exc, "invalid_op")
        with pytest.raises(DocumentError) as exc:
            session.apply_op("owner", {"key": "k"})
        _assert_code(exc, "invalid_op")

    def test_operations_since(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        session.apply_op("owner", {"key": "k1", "value": 1})
        session.apply_op("owner", {"key": "k2", "value": 2})
        assert [op["key"] for op in session.operations_since(1)] == ["k2"]


class TestBranches:
    """Fork / edit / merge / conflict resolution."""

    def _session_with_data(self) -> CollabSession:
        session = CollabSession("s1", "d1", "s", "owner")
        session.apply_op("owner", {"key": "entity:e1", "value": {"r": 1}})
        session.apply_op("owner", {"key": "entity:e2", "value": {"r": 2}})
        return session

    def test_fork_and_edit_independent(self) -> None:
        session = self._session_with_data()
        branch = session.fork_branch("owner", name="draft")
        session.edit_branch("owner", branch["branch_id"], {"key": "entity:e3", "value": 3})
        assert "entity:e3" not in session.state_dict()
        assert session.list_branches()[0]["name"] == "draft"

    def test_merge_new_key_from_branch_is_conflict(self) -> None:
        session = self._session_with_data()
        branch = session.fork_branch("owner")
        session.edit_branch("owner", branch["branch_id"], {"key": "entity:e3", "value": 3})
        conflicts = session.merge_branch("owner", branch["branch_id"])
        assert len(conflicts) == 1
        conflict = conflicts[0]
        assert conflict["key"] == "entity:e3"
        assert conflict["ours"] is None
        assert conflict["theirs"] == 3
        assert session.state_dict()["entity:e3"] == 3

    def test_merge_detects_concurrent_change(self) -> None:
        session = self._session_with_data()
        branch = session.fork_branch("owner")
        session.edit_branch("owner", branch["branch_id"], {"key": "entity:e1", "value": 99})
        session.apply_op("owner", {"key": "entity:e1", "value": {"r": 5}})
        conflicts = session.merge_branch("owner", branch["branch_id"])
        assert len(conflicts) == 1
        assert conflicts[0]["key"] == "entity:e1"
        assert session.pending_conflicts()[0]["resolved"] is False

    def test_resolve_conflict_ours_and_theirs(self) -> None:
        session = self._session_with_data()
        branch = session.fork_branch("owner")
        session.edit_branch("owner", branch["branch_id"], {"key": "entity:e1", "value": 99})
        session.apply_op("owner", {"key": "entity:e1", "value": {"r": 5}})
        conflicts = session.merge_branch("owner", branch["branch_id"])
        conflict = conflicts[0]
        session.resolve_conflict("owner", conflict["conflict_id"], "theirs")
        assert session.state_dict()["entity:e1"] == 99
        assert session.pending_conflicts() == []

    def test_resolve_unknown_or_duplicate(self) -> None:
        session = self._session_with_data()
        with pytest.raises(DocumentError) as exc:
            session.resolve_conflict("owner", "cf_x", "ours")
        _assert_code(exc, "conflict_not_found")

    def test_resolve_invalid_choice(self) -> None:
        session = self._session_with_data()
        branch = session.fork_branch("owner")
        session.edit_branch("owner", branch["branch_id"], {"key": "entity:e1", "value": 9})
        conflicts = session.merge_branch("owner", branch["branch_id"])
        with pytest.raises(DocumentError) as exc:
            session.resolve_conflict("owner", conflicts[0]["conflict_id"], "bogus")
        _assert_code(exc, "invalid_resolution")

    def test_merge_requires_manage(self) -> None:
        session = self._session_with_data()
        session.add_member("bob", "editor")
        branch = session.fork_branch("owner")
        with pytest.raises(DocumentError) as exc:
            session.merge_branch("bob", branch["branch_id"])
        _assert_code(exc, "permission_denied")

    def test_unknown_branch(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        with pytest.raises(DocumentError) as exc:
            session.merge_branch("owner", "br_nope")
        _assert_code(exc, "branch_not_found")


class TestAnnotations:
    """Annotation add / list / close."""

    def test_add_and_list(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        annotation = session.add_annotation("owner", "check the hole", ref="hole_1")
        assert annotation["ref"] == "hole_1"
        assert session.list_annotations()[0]["text"] == "check the hole"

    def test_close_annotation(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        annotation = session.add_annotation("owner", "todo")
        closed = session.close_annotation("owner", annotation["annotation_id"])
        assert closed["resolved"] is True

    def test_close_annotation_permission(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        session.add_member("bob", "editor")
        annotation = session.add_annotation("owner", "todo")
        with pytest.raises(DocumentError) as exc:
            session.close_annotation("bob", annotation["annotation_id"])
        _assert_code(exc, "permission_denied")

    def test_close_missing(self) -> None:
        session = CollabSession("s1", "d1", "s", "owner")
        with pytest.raises(DocumentError) as exc:
            session.close_annotation("owner", "ann_nope")
        _assert_code(exc, "annotation_not_found")


class TestBuildSeed:
    """Seed a session from a real document."""

    def test_build_seed_populates_registers(self) -> None:
        manager = DocumentManager()
        manager.create("seed.json", unit="mm")
        doc = manager.get_current()
        assert doc is not None
        doc.entities.create("line", {"start": [0, 0], "end": [10, 0]})
        doc.layers.create("Dims", color="#FF0000")
        doc.variables.set("width", 50)
        seed = build_seed(doc)
        assert any(key.startswith("entity:") for key in seed)
        assert "layer:Dims" in seed
        assert "variable:width" in seed

    def test_create_session_with_seed(self) -> None:
        manager = CollabManager()
        session = manager.create_session("d1", seed={"entity:e1": {"r": 1}})
        assert session.state_dict()["entity:e1"] == {"r": 1}
