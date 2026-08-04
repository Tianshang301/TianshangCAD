"""Session state management.

A session groups the documents open in one client (CLI or MCP) together
with command history and undo/redo stacks.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from tianshangcad.core.document import DocumentState


@dataclass
class SessionState:
    """State of a single client session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    active_files: dict[str, DocumentState] = field(default_factory=dict)
    current_file_id: str | None = None
    command_history: list[dict[str, Any]] = field(default_factory=list)
    undo_stack: list[dict[str, Any]] = field(default_factory=list)
    redo_stack: list[dict[str, Any]] = field(default_factory=list)

    def add_command(self, command: str, params: dict[str, Any], result: dict[str, Any]) -> None:
        """Record a command in history."""
        self.command_history.append({
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "params": params,
            "result": result,
        })

    def push_undo(self, state: dict[str, Any]) -> None:
        """Push a snapshot to the undo stack and clear the redo stack."""
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self) -> dict[str, Any] | None:
        """Pop and return the last undo snapshot."""
        if not self.undo_stack:
            return None
        state = self.undo_stack.pop()
        self.redo_stack.append(state)
        return state

    def redo(self) -> dict[str, Any] | None:
        """Pop and return the last redo snapshot."""
        if not self.redo_stack:
            return None
        state = self.redo_stack.pop()
        self.undo_stack.append(state)
        return state


class SessionManager:
    """Singleton session manager."""

    _instance: SessionManager | None = None
    _sessions: ClassVar[dict[str, SessionState]] = {}

    def __new__(cls) -> SessionManager:
        """Create the singleton instance on first use."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialize the singleton's per-instance state once."""
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.current_session_id: str | None = None

    @property
    def current_session(self) -> SessionState:
        """Return the current session, creating a default one if needed."""
        if self.current_session_id is None or self.current_session_id not in self._sessions:
            self.current_session_id = self.create_session().session_id
        return self._sessions[self.current_session_id]

    def create_session(self) -> SessionState:
        """Create a new session and make it current."""
        session = SessionState()
        self._sessions[session.session_id] = session
        self.current_session_id = session.session_id
        return session

    def get_session(self, session_id: str) -> SessionState | None:
        """Return a session by id (or ``None``)."""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        """Close a session, closing its documents."""
        session = self._sessions.get(session_id)
        if session is None:
            return
        for doc in session.active_files.values():
            doc.close()
        del self._sessions[session_id]
        if self.current_session_id == session_id:
            self.current_session_id = None

    def reset(self) -> None:
        """Drop all sessions (used by tests)."""
        self._sessions.clear()
        self.current_session_id = None
