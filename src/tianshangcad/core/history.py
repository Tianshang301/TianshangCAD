"""Snapshot-based undo/redo history."""

from __future__ import annotations

from typing import Any


class History:
    """A bounded snapshot stack with undo and redo support."""

    def __init__(self, max_depth: int = 50) -> None:
        """Initialize the history with a bounded depth."""
        if max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        self._max_depth = max_depth
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []

    def push(self, state: dict[str, Any]) -> None:
        """Record a new state snapshot (clears the redo stack)."""
        self._undo.append(state)
        if len(self._undo) > self._max_depth:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> dict[str, Any] | None:
        """Pop the previous snapshot for undo."""
        if not self._undo:
            return None
        state = self._undo.pop()
        self._redo.append(state)
        return state

    def redo(self) -> dict[str, Any] | None:
        """Pop a snapshot for redo."""
        if not self._redo:
            return None
        state = self._redo.pop()
        self._undo.append(state)
        return state

    def clear(self) -> None:
        """Clear both stacks."""
        self._undo.clear()
        self._redo.clear()

    @property
    def can_undo(self) -> bool:
        """Whether an undo is available."""
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        """Whether a redo is available."""
        return bool(self._redo)

    def __len__(self) -> int:
        """Return the number of undo snapshots."""
        return len(self._undo)
