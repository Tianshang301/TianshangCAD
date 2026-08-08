"""MCP collaboration tool tests."""

from __future__ import annotations

from tianshangcad.core.collab import CollabManager
from tianshangcad.core.document import DocumentManager
from tianshangcad.mcp.tools.collab import (
    TOOLS,
    CollabAnnotationInput,
    CollabBranchInput,
    CollabHistoryInput,
    CollabPermissionInput,
    CollabPresenceInput,
    CollabResolveInput,
    CollabSessionInput,
    CollabSyncInput,
    cad_collab_annotation,
    cad_collab_branch,
    cad_collab_history,
    cad_collab_permission,
    cad_collab_presence,
    cad_collab_resolve,
    cad_collab_session,
    cad_collab_sync,
)


def _make_session(seed: dict | None = None) -> str:
    mgr = DocumentManager()
    mgr.create("collab.json", unit="mm")
    doc = mgr.get_current()
    assert doc is not None
    result = cad_collab_session(
        CollabSessionInput(action="create", name="review", document_id=doc.file_id)
    )
    assert result.status == "success"
    return result.session_id


class TestSessionTool:
    def test_create_list_join_info_leave(self) -> None:
        session_id = _make_session()
        assert CollabManager().get_session(session_id).owner == "owner"

        listed = cad_collab_session(CollabSessionInput(action="list"))
        assert listed.status == "success"
        assert any(s["session_id"] == session_id for s in listed.sessions)

        joined = cad_collab_session(
            CollabSessionInput(action="join", session_id=session_id, user_id="bob")
        )
        assert joined.status == "success"

        info = cad_collab_session(
            CollabSessionInput(action="info", session_id=session_id, user_id="bob")
        )
        assert {m["user_id"] for m in info.members} == {"owner", "bob"}

        left = cad_collab_session(
            CollabSessionInput(action="leave", session_id=session_id, user_id="bob")
        )
        assert left.status == "success"

    def test_create_requires_document(self) -> None:
        result = cad_collab_session(CollabSessionInput(action="create", user_id="alice"))
        assert result.status == "error"

    def test_unknown_action(self) -> None:
        result = cad_collab_session(CollabSessionInput(action="explode", user_id="alice"))
        assert result.status == "error"

    def test_missing_session(self) -> None:
        result = cad_collab_session(CollabSessionInput(action="info", session_id="nope"))
        assert result.status == "error"


class TestBranchTool:
    def test_fork_edit_merge_list(self) -> None:
        session_id = _make_session()
        fork = cad_collab_branch(
            CollabBranchInput(action="fork", session_id=session_id, name="draft")
        )
        assert fork.status == "success"

        edit = cad_collab_branch(
            CollabBranchInput(
                action="edit",
                session_id=session_id,
                branch_id=fork.branch_id,
                key="entity:e9",
                value=3,
            )
        )
        assert edit.status == "success"

        listed = cad_collab_branch(CollabBranchInput(action="list", session_id=session_id))
        assert listed.status == "success"
        assert listed.branches[0]["name"] == "draft"

        merged = cad_collab_branch(
            CollabBranchInput(action="merge", session_id=session_id, branch_id=fork.branch_id)
        )
        assert merged.status == "success"
        assert merged.conflicts  # new key from branch is flagged

    def test_edit_requires_key(self) -> None:
        session_id = _make_session()
        result = cad_collab_branch(
            CollabBranchInput(action="edit", session_id=session_id, branch_id="br_x")
        )
        assert result.status == "error"


class TestAnnotationTool:
    def test_add_list_close(self) -> None:
        session_id = _make_session()
        added = cad_collab_annotation(
            CollabAnnotationInput(action="add", session_id=session_id, text="check hole")
        )
        assert added.status == "success"
        listed = cad_collab_annotation(CollabAnnotationInput(action="list", session_id=session_id))
        assert listed.status == "success"
        closed = cad_collab_annotation(
            CollabAnnotationInput(
                action="close",
                session_id=session_id,
                annotation_id=added.annotation_id,
            )
        )
        assert closed.status == "success"

    def test_add_requires_text(self) -> None:
        session_id = _make_session()
        result = cad_collab_annotation(
            CollabAnnotationInput(action="add", session_id=session_id)
        )
        assert result.status == "error"


class TestPresenceTool:
    def test_set_get_list(self) -> None:
        session_id = _make_session()
        set_result = cad_collab_presence(
            CollabPresenceInput(action="set", session_id=session_id, user_id="bob", status="busy")
        )
        assert set_result.status == "success"
        get_result = cad_collab_presence(
            CollabPresenceInput(action="get", session_id=session_id, user_id="bob")
        )
        assert get_result.presence[0]["status"] == "busy"
        list_result = cad_collab_presence(CollabPresenceInput(action="list", session_id=session_id))
        assert list_result.status == "success"

    def test_set_requires_user(self) -> None:
        session_id = _make_session()
        result = cad_collab_presence(
            CollabPresenceInput(action="set", session_id=session_id, user_id="")
        )
        assert result.status == "error"


class TestHistoryTool:
    def test_history_returns_ops(self) -> None:
        session_id = _make_session()
        cad_collab_sync(
            CollabSyncInput(session_id=session_id, ops=[{"key": "k1", "value": 1}], by_user="owner")
        )
        result = cad_collab_history(CollabHistoryInput(session_id=session_id))
        assert result.status == "success"
        assert result.count >= 1

    def test_history_after_seq(self) -> None:
        session_id = _make_session()
        cad_collab_sync(
            CollabSyncInput(
                session_id=session_id,
                ops=[{"key": "k1", "value": 1}, {"key": "k2", "value": 2}],
                by_user="owner",
            )
        )
        result = cad_collab_history(CollabHistoryInput(session_id=session_id, after_seq=1))
        assert result.count == 1
        assert result.operations[0]["key"] == "k2"


class TestResolveTool:
    def test_resolve_conflict(self) -> None:
        session_id = _make_session()
        branch = cad_collab_branch(
            CollabBranchInput(action="fork", session_id=session_id, by_user="owner")
        )
        cad_collab_branch(
            CollabBranchInput(
                action="edit",
                session_id=session_id,
                branch_id=branch.branch_id,
                key="entity:e1",
                value=99,
            )
        )
        cad_collab_sync(
            CollabSyncInput(
                session_id=session_id,
                ops=[{"key": "entity:e1", "value": 1}],
                by_user="owner",
            )
        )
        merged = cad_collab_branch(
            CollabBranchInput(action="merge", session_id=session_id, branch_id=branch.branch_id)
        )
        assert merged.conflicts
        resolved = cad_collab_resolve(
            CollabResolveInput(
                session_id=session_id,
                conflict_id=merged.conflicts[0]["conflict_id"],
                resolution="ours",
                by_user="owner",
            )
        )
        assert resolved.status == "success"
        assert resolved.pending == []

    def test_resolve_missing_conflict(self) -> None:
        session_id = _make_session()
        result = cad_collab_resolve(
            CollabResolveInput(session_id=session_id, conflict_id="cf_nope", resolution="ours")
        )
        assert result.status == "error"


class TestPermissionTool:
    def test_list_grant_check(self) -> None:
        session_id = _make_session()
        listed = cad_collab_permission(
            CollabPermissionInput(action="list", session_id=session_id)
        )
        assert listed.status == "success"

        granted = cad_collab_permission(
            CollabPermissionInput(
                action="grant",
                session_id=session_id,
                user_id="bob",
                role="editor",
                by_user="owner",
            )
        )
        assert granted.status == "success"

        checked = cad_collab_permission(
            CollabPermissionInput(
                action="check",
                session_id=session_id,
                user_id="bob",
                scope="document",
                permission="write",
            )
        )
        assert checked.allowed is True

    def test_grant_requires_manage(self) -> None:
        session_id = _make_session()
        cad_collab_session(
            CollabSessionInput(action="join", session_id=session_id, user_id="charlie")
        )
        result = cad_collab_permission(
            CollabPermissionInput(
                action="grant",
                session_id=session_id,
                user_id="dave",
                role="editor",
                by_user="charlie",
            )
        )
        assert result.status == "error"

    def test_check_unknown_permission(self) -> None:
        session_id = _make_session()
        result = cad_collab_permission(
            CollabPermissionInput(
                action="check",
                session_id=session_id,
                user_id="alice",
                permission="explode",
            )
        )
        assert result.status == "error"


class TestSyncTool:
    def test_sync_applies_and_returns_state(self) -> None:
        session_id = _make_session()
        result = cad_collab_sync(
            CollabSyncInput(
                session_id=session_id,
                ops=[{"key": "entity:e1", "value": {"r": 1}}],
                since=0,
                by_user="owner",
            )
        )
        assert result.status == "success"
        assert len(result.applied) == 1
        assert result.state["entity:e1"] == {"r": 1}
        assert len(result.deltas) == 1

    def test_sync_without_state(self) -> None:
        session_id = _make_session()
        result = cad_collab_sync(
            CollabSyncInput(
                session_id=session_id,
                ops=[{"key": "k", "value": 1}],
                include_state=False,
                by_user="owner",
            )
        )
        assert result.status == "success"
        assert result.state == {}

    def test_sync_scope_write_guard(self) -> None:
        session_id = _make_session()
        cad_collab_session(CollabSessionInput(action="join", session_id=session_id, user_id="bob"))
        result = cad_collab_sync(
            CollabSyncInput(
                session_id=session_id,
                ops=[{"key": "entity:e1", "value": 1}],
                by_user="bob",
            )
        )
        assert result.status == "error"

    def test_sync_missing_session(self) -> None:
        result = cad_collab_sync(CollabSyncInput(session_id="nope"))
        assert result.status == "error"


def test_tools_registered() -> None:
    names = {name for name, _ in TOOLS}
    assert names == {"cad_collab"}
