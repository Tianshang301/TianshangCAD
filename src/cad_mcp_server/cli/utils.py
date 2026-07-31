"""Shared CLI helpers."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, NoReturn, TypeVar

import typer

from cad_mcp_server.core.document import DocumentManager, DocumentState
from cad_mcp_server.core.session import SessionManager
from cad_mcp_server.utils.errors import CADError
from cad_mcp_server.utils.validators import parse_point as _parse_point

F = TypeVar("F", bound=Callable[..., Any])


def catch_errors(func: F) -> F:
    """Decorate a typer command so ``CADError`` becomes an error message."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except CADError as exc:
            typer.echo(f"Error: {exc.message}", err=True)
            raise typer.Exit(code=1) from exc

    return wrapper  # type: ignore[return-value]


def get_document() -> DocumentState:
    """Return the current document (raises ``DocumentError`` when missing)."""
    return DocumentManager().get_current()


def parse_point(text: str) -> list[float]:
    """Parse a 3D point string such as ``"1,2,3"``."""
    return _parse_point(text, 3)


def fail(message: str) -> NoReturn:
    """Print an error message and exit with code 1."""
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


def push_undo() -> None:
    """Snapshot the current document onto the session undo stack."""
    doc = get_document()
    session = SessionManager().current_session
    session.undo_stack.append(snapshot_document(doc))
    session.redo_stack.clear()


def snapshot_document(doc: DocumentState) -> dict[str, Any]:
    """Capture entities + layers of ``doc`` as a snapshot."""
    return {
        "entities": doc.entities.snapshot(),
        "layers": doc.layers.snapshot(),
    }


def restore_document(doc: DocumentState, snapshot: dict[str, Any]) -> None:
    """Restore entities + layers of ``doc`` from a snapshot."""
    doc.entities.restore(snapshot["entities"])
    doc.layers.restore(snapshot["layers"])
