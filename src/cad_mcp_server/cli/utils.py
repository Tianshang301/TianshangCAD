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
from cad_mcp_server.utils.validators import parse_point_list as _parse_point_list

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
    """Parse a 3D point string such as ``"1,2,3"`` after variable interpolation."""
    return _parse_point(interpolate(text), 3)


def parse_point_list(text: str) -> list[list[float]]:
    """Parse a space separated point list after variable interpolation."""
    return _parse_point_list(interpolate(text))


def interpolate(text: str) -> str:
    """Interpolate ``{name}`` tokens using the current document's variables."""
    doc = get_document()
    return doc.variables.interpolate(text)


def parse_float(text: str) -> float:
    """Interpolate ``text`` then convert it to a float."""
    return float(interpolate(text))


def parse_int(text: str) -> int:
    """Interpolate ``text`` then convert it to an int."""
    return int(interpolate(text))


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
    """Capture entities + layers + variables of ``doc`` as a snapshot."""
    return {
        "entities": doc.entities.snapshot(),
        "layers": doc.layers.snapshot(),
        "variables": doc.variables.snapshot(),
    }


def restore_document(doc: DocumentState, snapshot: dict[str, Any]) -> None:
    """Restore entities + layers + variables of ``doc`` from a snapshot."""
    doc.entities.restore(snapshot["entities"])
    doc.layers.restore(snapshot["layers"])
    if "variables" in snapshot:
        doc.variables.restore(snapshot["variables"])
