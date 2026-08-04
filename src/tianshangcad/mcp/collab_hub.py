"""Multi-client WebSocket subscription hub.

Phase 9 (v0.9.0) Task A ships the collaboration sync protocol with a
per-connection handler; this module provides the shared fan-out state that
ties connections to the same :class:`~tianshangcad.core.collab.CollabSession`
together. ``CollabHub`` maps a ``session_id`` to the set of outbound queues
registered by connected clients. When one client applies CRDT operations via
``cad_collab_sync``, the server publishes the resulting deltas to every other
subscriber of that session.

The hub is deliberately dependency-free: subscribers are plain
``asyncio.Queue`` objects, so it is unit-testable without ``websockets`` and
keeps the default install unburdened.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any


class CollabHub:
    """Fan-out registry for WebSocket collaboration subscribers.

    Each connected subscriber registers the ``session_id`` it is interested in
    along with an :class:`asyncio.Queue` that its single writer task drains.
    :meth:`publish` JSON-encodes a payload once and pushes a copy to every
    queue registered for a session (optionally excluding the originator's
    queue, which already received its own live response).
    """

    def __init__(self) -> None:
        """Initialize an empty subscription registry."""
        self._subscribers: dict[str, set[asyncio.Queue[str]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str, queue: asyncio.Queue[str]) -> None:
        """Register ``queue`` as a subscriber of ``session_id``."""
        async with self._lock:
            self._subscribers.setdefault(session_id, set()).add(queue)

    async def unsubscribe(self, session_id: str, queue: asyncio.Queue[str]) -> None:
        """Remove ``queue`` from ``session_id``, dropping empty buckets."""
        async with self._lock:
            bucket = self._subscribers.get(session_id)
            if bucket is None:
                return
            bucket.discard(queue)
            if not bucket:
                self._subscribers.pop(session_id, None)

    def subscriber_count(self, session_id: str) -> int:
        """Return the number of live subscribers for ``session_id``."""
        return len(self._subscribers.get(session_id, set()))

    def session_ids(self) -> list[str]:
        """Return every session that currently has subscribers."""
        return list(self._subscribers.keys())

    async def publish(
        self,
        session_id: str,
        payload: dict[str, Any],
        *,
        exclude: asyncio.Queue[str] | None = None,
    ) -> int:
        """Fan a JSON-encoded ``payload`` out to ``session_id`` subscribers.

        Returns the number of subscribers that received the message. The
        origin's own ``exclude`` queue is omitted (it already holds a live
        response).
        """
        message = json.dumps(payload)
        targets = set(self._subscribers.get(session_id, set()))
        if exclude is not None:
            targets.discard(exclude)
        for queue in targets:
            queue.put_nowait(message)
        return len(targets)
