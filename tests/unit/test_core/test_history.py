"""Tests for the snapshot history."""

from __future__ import annotations

from tianshangcad.core.history import History


class TestHistory:
    """Undo/redo history tests."""

    def test_push_undo_redo(self) -> None:
        history = History()
        history.push({"v": 1})
        history.push({"v": 2})
        assert history.undo() == {"v": 2}
        assert history.redo() == {"v": 2}
        assert history.undo() == {"v": 2}
        assert history.undo() == {"v": 1}
        assert history.undo() is None

    def test_push_clears_redo(self) -> None:
        history = History()
        history.push({"v": 1})
        history.undo()
        history.push({"v": 2})
        assert history.can_redo is False

    def test_bounded_depth(self) -> None:
        history = History(max_depth=3)
        for i in range(10):
            history.push({"v": i})
        assert len(history) == 3
        assert history.undo() == {"v": 9}

    def test_clear(self) -> None:
        history = History()
        history.push({"v": 1})
        history.clear()
        assert not history.can_undo
        assert history.undo() is None

    def test_flags(self) -> None:
        history = History()
        assert not history.can_undo
        history.push({"v": 1})
        assert history.can_undo
        history.undo()
        assert history.can_redo
