"""Collaboration commands: sessions, branches, annotations, RBAC and sync."""

from __future__ import annotations

import typer

from cad_mcp_server.cli.utils import catch_errors, get_document
from cad_mcp_server.core.collab import (
    CollabAction,
    CollabManager,
    ResourceScope,
    build_seed,
)

app = typer.Typer(help="Real-time collaboration commands")


def _manager() -> CollabManager:
    return CollabManager()


def _echo_json(value: dict[str, object]) -> None:
    import json

    typer.echo(json.dumps(value, ensure_ascii=False, indent=2))


@app.command("create")
@catch_errors
def cmd_create(
    name: str = typer.Option("session", "--name", "-n", help="Session name"),
    owner: str = typer.Option("owner", "--owner", help="Session owner"),
) -> None:
    """Create a collaboration session over the current document."""
    doc = get_document()
    session = _manager().create_session(
        document_id=doc.file_id, name=name, owner=owner, seed=build_seed(doc)
    )
    typer.echo(f"Session {session.session_id} created for {doc.filename}")


@app.command("list")
@catch_errors
def cmd_list() -> None:
    """List collaboration sessions."""
    sessions = _manager().list_sessions()
    if not sessions:
        typer.echo("No collaboration sessions")
        return
    for entry in sessions:
        typer.echo(
            f"{entry['session_id']}  {entry['name']}  "
            f"members={entry['member_count']}  branches={entry['branch_count']}"
        )


@app.command("annotate")
@catch_errors
def cmd_annotate(
    session_id: str = typer.Argument(..., help="Session id"),
    text: str = typer.Argument(..., help="Annotation text"),
    user: str = typer.Option("owner", "--user", help="Author"),
) -> None:
    """Add an annotation to a session."""
    annotation = _manager().get_session(session_id).add_annotation(user, text)
    typer.echo(f"Annotation {annotation['annotation_id']} added")


@app.command("sync")
@catch_errors
def cmd_sync(
    session_id: str = typer.Argument(..., help="Session id"),
    user: str = typer.Option("owner", "--user", help="Acting user"),
) -> None:
    """Print the live CRDT state of a session."""
    session = _manager().get_session(session_id)
    _echo_json(session.state_dict())


@app.command("perm")
@catch_errors
def cmd_perm(
    session_id: str = typer.Argument(..., help="Session id"),
    user_id: str = typer.Argument(..., help="Target user"),
    role: str = typer.Option("editor", "--role", help="Role to grant"),
    by_user: str = typer.Option("owner", "--by", help="Granting user"),
) -> None:
    """Grant a role to a member."""
    session = _manager().get_session(session_id)
    session.require(by_user, ResourceScope.SETTINGS, CollabAction.MANAGE)
    session.set_role(user_id, role)
    typer.echo(f"{user_id} granted {role} in {session_id}")
