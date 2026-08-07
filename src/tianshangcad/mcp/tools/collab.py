"""Collaboration tools: sessions, branches, annotations, presence, RBAC, sync.

Phase 9 (v0.9.0) Task A exposes the CRDT collaboration primitives to MCP
clients. Every write goes through the RBAC matrix in
``core.collab.has_permission``; unknown users default to the session owner
until a real identity transport is configured.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from tianshangcad.core.collab import (
    CollabAction,
    CollabManager,
    ResourceScope,
    build_seed,
    can_act,
)
from tianshangcad.core.document import DocumentManager
from tianshangcad.utils.errors import CADError


class CollabSessionInput(BaseModel):
    """Input for session lifecycle operations."""

    action: str = Field(..., description="create | list | join | leave | info")
    name: str | None = Field(None, description="Session name (create)")
    document_id: str | None = Field(None, description="Document to collaborate on (create)")
    session_id: str | None = Field(None, description="Session id (join/info/leave)")
    user_id: str = Field("owner", description="Acting user (identity)")


class CollabSessionOutput(BaseModel):
    """Output for session operations."""

    session_id: str = Field("", description="Session identifier")
    sessions: list[dict[str, Any]] = Field(default_factory=list, description="Session summaries")
    members: list[dict[str, Any]] = Field(default_factory=list, description="Members with roles")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class CollabBranchInput(BaseModel):
    """Input for branch operations."""

    action: str = Field(..., description="fork | edit | merge | list")
    session_id: str = Field(..., description="Session id")
    name: str | None = Field(None, description="Branch name (fork)")
    branch_id: str | None = Field(None, description="Branch id (edit/merge)")
    key: str | None = Field(None, description="Register key (edit)")
    value: Any = Field(None, description="Register value (edit)")
    delete: bool = Field(False, description="Delete instead of write (edit)")
    by_user: str = Field("owner", description="Acting user")


class CollabBranchOutput(BaseModel):
    """Output for branch operations."""

    branch_id: str = Field("", description="Branch identifier")
    branches: list[dict[str, Any]] = Field(default_factory=list, description="Branch summaries")
    conflicts: list[dict[str, Any]] = Field(default_factory=list, description="Merge conflicts")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class CollabAnnotationInput(BaseModel):
    """Input for annotation operations."""

    action: str = Field(..., description="add | list | close")
    session_id: str = Field(..., description="Session id")
    text: str | None = Field(None, description="Annotation text (add)")
    scope: str = Field("scene", description="Annotation scope (add)")
    ref: str | None = Field(None, description="Optional referenced key/id (add)")
    annotation_id: str | None = Field(None, description="Annotation id (close)")
    by_user: str = Field("owner", description="Acting user")


class CollabAnnotationOutput(BaseModel):
    """Output for annotation operations."""

    annotation_id: str = Field("", description="Annotation identifier")
    annotations: list[dict[str, Any]] = Field(default_factory=list, description="Annotations")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class CollabPresenceInput(BaseModel):
    """Input for presence operations."""

    action: str = Field(..., description="set | get | list")
    session_id: str = Field(..., description="Session id")
    user_id: str | None = Field(None, description="Target user")
    status: str | None = Field(None, description="Presence status (online/busy/away)")
    cursor: str | None = Field(None, description="Cursor position, e.g. entity id")


class CollabPresenceOutput(BaseModel):
    """Output for presence operations."""

    presence: list[dict[str, Any]] = Field(default_factory=list, description="Presence records")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class CollabHistoryInput(BaseModel):
    """Input for history operations."""

    session_id: str = Field(..., description="Session id")
    by_user: str = Field("owner", description="User requesting history (RBAC check)")
    after_seq: int = Field(0, description="Only return operations after this seq")
    limit: int = Field(100, ge=1, le=1000, description="Max operations to return")


class CollabHistoryOutput(BaseModel):
    """Output for history operations."""

    operations: list[dict[str, Any]] = Field(default_factory=list, description="Applied operations")
    count: int = Field(0, description="Number of returned operations")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class CollabResolveInput(BaseModel):
    """Input for conflict resolution."""

    session_id: str = Field(..., description="Session id")
    conflict_id: str = Field(..., description="Conflict id to resolve")
    resolution: str = Field(..., description="ours | theirs | latest")
    by_user: str = Field("owner", description="Acting user")


class CollabResolveOutput(BaseModel):
    """Output for conflict resolution."""

    conflict_id: str = Field(..., description="Resolved conflict id")
    resolution: str = Field(..., description="Chosen resolution")
    pending: list[dict[str, Any]] = Field(default_factory=list, description="Remaining conflicts")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class CollabPermissionInput(BaseModel):
    """Input for RBAC operations."""

    action: str = Field(..., description="list | grant | check")
    session_id: str = Field(..., description="Session id")
    user_id: str | None = Field(None, description="Target user (grant/check)")
    role: str | None = Field(None, description="Role to grant: viewer|editor|admin|owner")
    scope: str = Field("document", description="Resource scope for check")
    permission: str = Field("read", description="Action for check: read|write|manage|delete")
    by_user: str = Field("owner", description="Acting user")


class CollabPermissionOutput(BaseModel):
    """Output for RBAC operations."""

    members: list[dict[str, Any]] = Field(default_factory=list, description="Members with roles")
    allowed: bool | None = Field(None, description="Permission check result")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


class CollabSyncInput(BaseModel):
    """Input for CRDT sync."""

    session_id: str = Field(..., description="Session id")
    since: int = Field(0, description="Only return operations after this seq")
    ops: list[dict[str, Any]] = Field(default_factory=list, description="Operations to apply")
    include_state: bool = Field(True, description="Include the full live state")
    by_user: str = Field("owner", description="Acting user")


class CollabSyncOutput(BaseModel):
    """Output for CRDT sync."""

    session_id: str = Field(..., description="Session id")
    applied: list[dict[str, Any]] = Field(default_factory=list, description="Applied op records")
    deltas: list[dict[str, Any]] = Field(default_factory=list, description="Ops after `since`")
    state: dict[str, Any] = Field(default_factory=dict, description="Live register values")
    status: str = Field(..., description="Operation status: success / error")
    message: str | None = Field(None, description="Status description")


def _manager() -> CollabManager:
    return CollabManager()


def _scopes_from_keys() -> dict[str, ResourceScope]:
    return {
        "document": ResourceScope.DOCUMENT,
        "scene": ResourceScope.SCENE,
        "assembly": ResourceScope.ASSEMBLY,
        "settings": ResourceScope.SETTINGS,
    }


def cad_collab_session(input: CollabSessionInput) -> CollabSessionOutput:
    """Manage collaboration sessions.

    管理协作会话。``action`` 为 create（需 document_id）、list、join、
    info 或 leave。A session groups multiple users editing one document via
    CRDT operations; ``session_id`` returned here feeds the other
    ``cad_collab_*`` tools.

    When not to use: for single-user work you do NOT need a session — use
    the plain CRUD tools (``cad_file_create`` / ``cad_object_create``)
    instead. ``action=create`` requires a document id from
    ``cad_file_list``; joining a session that does not exist is an error.
    """
    try:
        manager = _manager()
        if input.action == "create":
            if not input.document_id:
                return CollabSessionOutput(status="error", message="document_id is required")
            doc = DocumentManager()._require(input.document_id)
            session = manager.create_session(
                document_id=input.document_id,
                name=input.name or "session",
                owner=input.user_id,
                seed=build_seed(doc),
            )
            return CollabSessionOutput(
                session_id=session.session_id,
                status="success",
                message=f"Session {session.session_id} created",
            )
        if input.action == "list":
            return CollabSessionOutput(
                sessions=manager.list_sessions(), status="success", message="ok"
            )
        session = manager.get_session(input.session_id or "")
        if input.action == "join":
            manager.join_session(session.session_id, input.user_id)
            return CollabSessionOutput(
                session_id=session.session_id, status="success", message=f"{input.user_id} joined"
            )
        if input.action == "leave":
            session.presence.pop(input.user_id, None)
            session.members.pop(input.user_id, None)
            return CollabSessionOutput(
                session_id=session.session_id, status="success", message=f"{input.user_id} left"
            )
        if input.action == "info":
            return CollabSessionOutput(
                session_id=session.session_id,
                members=[
                    {"user_id": user, "role": role.value}
                    for user, role in session.members.items()
                ],
                status="success",
                message=session.name,
            )
        return CollabSessionOutput(status="error", message=f"Unknown action: {input.action}")
    except CADError as exc:
        return CollabSessionOutput(status="error", message=exc.message)


def cad_collab_branch(input: CollabBranchInput) -> CollabBranchOutput:
    """Fork, edit, merge and list document branches.

    文档分支操作。``action`` 为 fork（新建分支）、edit（写入/删除 register
    键值）、merge（合并，可返回冲突）或 list。Branches let concurrent
    editors isolate changes before reconciling via ``cad_collab_resolve``.

    When not to use: branches add overhead; prefer a single shared session
    (``cad_collab_sync``) unless you genuinely need isolated edits. A merge
    that finds conflicts does not auto-apply — call ``cad_collab_resolve``
    for each conflict id first.
    """
    try:
        session = _manager().get_session(input.session_id)
        if input.action == "fork":
            branch = session.fork_branch(input.by_user, name=input.name or "branch")
            return CollabBranchOutput(
                branch_id=branch["branch_id"],
                status="success",
                message=f"Branch {branch['branch_id']} forked",
            )
        if input.action == "edit":
            if not input.branch_id or not input.key:
                return CollabBranchOutput(
                    status="error", message="branch_id and key are required"
                )
            op: dict[str, Any] = {"key": input.key}
            if input.delete:
                op["delete"] = True
            else:
                op["value"] = input.value
            session.edit_branch(input.by_user, input.branch_id, op)
            return CollabBranchOutput(
                branch_id=input.branch_id, status="success", message="branch edited"
            )
        if input.action == "merge":
            if not input.branch_id:
                return CollabBranchOutput(status="error", message="branch_id is required")
            conflicts = session.merge_branch(input.by_user, input.branch_id)
            return CollabBranchOutput(
                branch_id=input.branch_id,
                conflicts=conflicts,
                status="success",
                message=f"Merged branch {input.branch_id}; {len(conflicts)} conflicts",
            )
        if input.action == "list":
            return CollabBranchOutput(
                branches=session.list_branches(), status="success", message="ok"
            )
        return CollabBranchOutput(status="error", message=f"Unknown action: {input.action}")
    except CADError as exc:
        return CollabBranchOutput(status="error", message=exc.message)


def cad_collab_annotation(input: CollabAnnotationInput) -> CollabAnnotationOutput:
    """Add, list and close annotations on a session.

    会话批注。``action`` 为 add（文本 + 可选 scope/ref）、list 或 close。
    Annotations are lightweight review comments attached to a session scope
    (e.g. a geometry key), independent of the CRDT register data.

    When not to use: for content changes use ``cad_collab_branch`` (edit)
    or the document CRUD tools; annotations are only for comments. Closing
    an annotation that does not exist is an error.
    """
    try:
        session = _manager().get_session(input.session_id)
        if input.action == "add":
            if not input.text:
                return CollabAnnotationOutput(status="error", message="text is required")
            annotation = session.add_annotation(
                input.by_user, input.text, scope=input.scope, ref=input.ref
            )
            return CollabAnnotationOutput(
                annotation_id=annotation["annotation_id"],
                status="success",
                message="annotation added",
            )
        if input.action == "list":
            return CollabAnnotationOutput(
                annotations=session.list_annotations(), status="success", message="ok"
            )
        if input.action == "close":
            if not input.annotation_id:
                return CollabAnnotationOutput(
                    status="error", message="annotation_id is required"
                )
            annotation = session.close_annotation(input.by_user, input.annotation_id)
            return CollabAnnotationOutput(
                annotation_id=annotation["annotation_id"],
                status="success",
                message="annotation closed",
            )
        return CollabAnnotationOutput(status="error", message=f"Unknown action: {input.action}")
    except CADError as exc:
        return CollabAnnotationOutput(status="error", message=exc.message)


def cad_collab_presence(input: CollabPresenceInput) -> CollabPresenceOutput:
    """Set, get and list presence across a session.

    会话在线状态。``action`` 为 set（更新 status/cursor）、get（查单用户）
    或 list（全部）。Presence drives who-is-online indicators; it is
    ephemeral and not part of the document state.

    When not to use: presence is not persisted and does not affect
    geometry — for actual edits use ``cad_collab_sync``. ``action=set``
    requires ``user_id``.
    """
    try:
        session = _manager().get_session(input.session_id)
        if input.action == "set":
            if not input.user_id:
                return CollabPresenceOutput(status="error", message="user_id is required")
            session.set_presence(
                input.user_id, status=input.status or "online", cursor=input.cursor
            )
            return CollabPresenceOutput(
                presence=[session.presence[input.user_id]],
                status="success",
                message="presence updated",
            )
        if input.action == "get":
            if not input.user_id:
                return CollabPresenceOutput(status="error", message="user_id is required")
            record = session.presence.get(input.user_id)
            return CollabPresenceOutput(
                presence=[record] if record else [],
                status="success",
                message="ok",
            )
        if input.action == "list":
            return CollabPresenceOutput(
                presence=list(session.presence.values()), status="success", message="ok"
            )
        return CollabPresenceOutput(status="error", message=f"Unknown action: {input.action}")
    except CADError as exc:
        return CollabPresenceOutput(status="error", message=exc.message)


def cad_collab_history(input: CollabHistoryInput) -> CollabHistoryOutput:
    """Return the applied operation history of a session.

    会话操作历史。Returns CRDT operations applied since ``after_seq``
    (0 = all), capped by ``limit``, newest included. Useful for auditing
    who changed what and for incremental ``cad_collab_sync`` catch-up.

    When not to use: to get the current document state (not the edit log)
    use ``cad_collab_sync`` with ``include_state=true``. History is bounded
    to the in-memory ring; very old operations may already be evicted.
    """
    try:
        session = _manager().get_session(input.session_id)
        session.require(
            input.by_user,
            ResourceScope.DOCUMENT,
            CollabAction.READ,
        )
        ops = session.operations_since(input.after_seq)
        ops = ops[-input.limit :]
        return CollabHistoryOutput(
            operations=ops, count=len(ops), status="success", message="ok"
        )
    except CADError as exc:
        return CollabHistoryOutput(status="error", message=exc.message)


def cad_collab_resolve(input: CollabResolveInput) -> CollabResolveOutput:
    """Resolve a branch-merge conflict explicitly.

    解决分支合并冲突。``resolution`` 为 ours（保留本地）、theirs（采用合并
    分支）或 latest（采用较新的操作）。After resolving, remaining conflicts
    are returned in ``pending``.

    When not to use: if there are no pending conflicts this is a no-op that
    errors on an unknown ``conflict_id`` — check ``cad_collab_branch``
    (merge) output first. For normal non-conflicting edits you never need
    this tool.
    """
    try:
        session = _manager().get_session(input.session_id)
        conflict = session.resolve_conflict(input.by_user, input.conflict_id, input.resolution)
        return CollabResolveOutput(
            conflict_id=conflict["conflict_id"],
            resolution=conflict["resolution"],
            pending=session.pending_conflicts(),
            status="success",
            message=f"Conflict {input.conflict_id} resolved as {input.resolution}",
        )
    except CADError as exc:
        return CollabResolveOutput(
            conflict_id=input.conflict_id,
            resolution=input.resolution,
            status="error",
            message=exc.message,
        )


def cad_collab_permission(input: CollabPermissionInput) -> CollabPermissionOutput:
    """List, grant and check roles within a session.

    会话 RBAC。``action`` 为 list、grant（给用户分配 role:
    viewer/editor/admin/owner）或 check（按 scope+permission 判定是否允许）。
    RBAC gates which operations a user may run in a session.

    When not to use: for single-user sessions RBAC is unnecessary — the
    acting user defaults to ``owner``. Roles only matter when multiple
    users join via ``cad_collab_session``.
    """
    try:
        session = _manager().get_session(input.session_id)
        if input.action == "list":
            return CollabPermissionOutput(
                members=[
                    {"user_id": user, "role": role.value}
                    for user, role in session.members.items()
                ],
                status="success",
                message="ok",
            )
        if input.action == "grant":
            if not input.user_id or not input.role:
                return CollabPermissionOutput(status="error", message="user_id and role required")
            session.require(input.by_user, ResourceScope.SETTINGS, CollabAction.MANAGE)
            session.set_role(input.user_id, input.role)
            return CollabPermissionOutput(
                members=[
                    {"user_id": user, "role": role.value}
                    for user, role in session.members.items()
                ],
                status="success",
                message=f"{input.user_id} granted {input.role}",
            )
        if input.action == "check":
            if not input.user_id:
                return CollabPermissionOutput(status="error", message="user_id is required")
            role = session.role_of(input.user_id)
            scope = _scopes_from_keys().get(
                input.scope, ResourceScope.DOCUMENT
            )
            try:
                action = CollabAction(input.permission)
            except ValueError:
                return CollabPermissionOutput(
                    status="error",
                    message=f"Unknown permission: {input.permission}",
                )
            return CollabPermissionOutput(
                allowed=can_act(role, scope, action),
                status="success",
                message=f"role={role.value}",
            )
        return CollabPermissionOutput(status="error", message=f"Unknown action: {input.action}")
    except CADError as exc:
        return CollabPermissionOutput(status="error", message=exc.message)


def cad_collab_sync(input: CollabSyncInput) -> CollabSyncOutput:
    """Push operations and/or pull the delta + state of a session.

    A transport-agnostic sync primitive: apply ``ops`` (RBAC-guarded),
    then return every operation after ``since`` plus (optionally) the live
    CRDT register map. WebSocket clients use the same entry point.
    """
    try:
        session = _manager().get_session(input.session_id)
        applied: list[dict[str, Any]] = []
        for op in input.ops:
            scope = _scopes_from_keys().get(
                str(op.get("scope", "document")), ResourceScope.DOCUMENT
            )
            applied.append(session.apply_op(input.by_user, op, scope=scope))
        deltas = session.operations_since(input.since)
        state = session.state_dict() if input.include_state else {}
        return CollabSyncOutput(
            session_id=session.session_id,
            applied=applied,
            deltas=deltas,
            state=state,
            status="success",
            message=f"applied {len(applied)} ops; {len(deltas)} deltas",
        )
    except CADError as exc:
        return CollabSyncOutput(
            session_id=input.session_id, status="error", message=exc.message
        )


#: Ordered (name, callable) pairs registered with the MCP server.
TOOLS: list[tuple[str, Any]] = [
    ("cad_collab_session", cad_collab_session),
    ("cad_collab_branch", cad_collab_branch),
    ("cad_collab_annotation", cad_collab_annotation),
    ("cad_collab_presence", cad_collab_presence),
    ("cad_collab_history", cad_collab_history),
    ("cad_collab_resolve", cad_collab_resolve),
    ("cad_collab_permission", cad_collab_permission),
    ("cad_collab_sync", cad_collab_sync),
]
