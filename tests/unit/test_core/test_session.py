"""Tests for session state management."""

from __future__ import annotations

from cad_mcp_server.core.session import SessionManager, SessionState


class TestSessionManager:
    """Session lifecycle tests."""

    def test_default_session_created_lazily(self) -> None:
        manager = SessionManager()
        session = manager.current_session
        assert isinstance(session, SessionState)
        assert session.session_id

    def test_create_and_get(self) -> None:
        manager = SessionManager()
        session = manager.create_session()
        assert manager.get_session(session.session_id) is session

    def test_current_session_switches(self) -> None:
        manager = SessionManager()
        first = manager.create_session()
        second = manager.create_session()
        assert manager.current_session.session_id == second.session_id
        assert first.session_id != second.session_id

    def test_close_session(self) -> None:
        manager = SessionManager()
        session = manager.create_session()
        manager.close_session(session.session_id)
        assert manager.get_session(session.session_id) is None

    def test_reset(self) -> None:
        manager = SessionManager()
        manager.create_session()
        manager.reset()
        assert manager.get_session.__self__._sessions == {}

    def test_singleton(self) -> None:
        assert SessionManager() is SessionManager()


class TestUndoRedo:
    """Undo/redo stack tests."""

    def test_push_undo_redo(self) -> None:
        state = SessionState()
        state.push_undo({"n": 1})
        state.push_undo({"n": 2})
        assert state.undo() == {"n": 2}
        assert state.redo() == {"n": 2}
        assert state.undo() == {"n": 2}

    def test_undo_empty(self) -> None:
        state = SessionState()
        assert state.undo() is None

    def test_push_clears_redo(self) -> None:
        state = SessionState()
        state.push_undo({"n": 1})
        state.undo()
        state.push_undo({"n": 2})
        assert state.redo() is None

    def test_add_command(self) -> None:
        state = SessionState()
        state.add_command("draw circle", {"radius": 5}, {"status": "success"})
        assert len(state.command_history) == 1
        assert state.command_history[0]["command"] == "draw circle"
