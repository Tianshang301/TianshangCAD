"""Concurrency and soak stress tests.

Covered here are the stability properties that the functional unit tests do
not: many threads hammering the flat MCP tool wrappers and the singleton
session state, many concurrent WebSocket-hub subscribers fanning out without
dropping messages, and create/delete soak loops asserting the entity store
returns to its baseline (no leak).

The module is gated by the ``stress`` marker so the default CI suite stays
fast; the dedicated ``stress`` job runs ``pytest -m stress``.
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from tianshangcad.core.document import DocumentManager
from tianshangcad.core.entity import EntityManager
from tianshangcad.core.session import SessionManager
from tianshangcad.mcp.collab_hub import CollabHub
from tianshangcad.mcp.tools.crud import (
    FileCreateInput,
    FileCreateOutput,
    cad_file_create,
)

pytestmark = pytest.mark.stress

THREADS = 8
CALLS_PER_THREAD = 20


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class TestConcurrentFlatTools:
    """Parallel calls through the flat single-input tool wrappers."""

    def test_many_concurrent_file_creates(self) -> None:
        def one(i: int) -> FileCreateOutput:
            return cad_file_create(FileCreateInput(filename=f"stress_{i}.json", unit="mm"))

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            results = list(pool.map(one, range(THREADS * CALLS_PER_THREAD)))

        assert all(r.status == "success" for r in results)
        ids = [r.file_id for r in results]
        assert len(ids) == len(set(ids)), "file ids must be unique"
        assert DocumentManager()._session.current_file_id in ids

    def test_concurrent_session_create_close(self) -> None:
        def one(_: int) -> str:
            session = SessionManager().create_session()
            SessionManager().close_session(session.session_id)
            return session.session_id

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            ids = list(pool.map(one, range(THREADS * CALLS_PER_THREAD)))

        assert len(ids) == len(set(ids))


class TestHubFanOut:
    """WebSocket hub fan-out with many concurrent subscribers/publishers."""

    def test_fanout_delivers_every_message(self) -> None:
        async def scenario() -> None:
            hub = CollabHub()
            clients = 40
            queues = [asyncio.Queue() for _ in range(clients)]
            for queue in queues:
                await hub.subscribe("s1", queue)

            delivered = await hub.publish("s1", {"type": "deltas", "k": 1})
            assert delivered == clients
            for queue in queues:
                assert queue.qsize() == 1
                assert not queue.empty()

            for queue in queues:
                await hub.unsubscribe("s1", queue)
            assert hub.subscriber_count("s1") == 0
            assert hub.session_ids() == []

        _run(scenario())

    def test_concurrent_publishers_no_loss(self) -> None:
        async def scenario() -> None:
            hub = CollabHub()
            subscribers = 10
            publishers = 20
            queues = [asyncio.Queue() for _ in range(subscribers)]
            for queue in queues:
                await hub.subscribe("s2", queue)

            async def publish(n: int) -> int:
                return await hub.publish("s2", {"type": "deltas", "n": n})

            counts = await asyncio.gather(*(publish(n) for n in range(publishers)))
            assert all(c == subscribers for c in counts)
            for queue in queues:
                assert queue.qsize() == publishers

        _run(scenario())


class TestSoak:
    """Create/delete loops that would expose state leaks."""

    def test_entity_create_delete_returns_to_baseline(self) -> None:
        manager = DocumentManager()
        manager.create("soak.json")
        entities = EntityManager()
        for i in range(500):
            entity_id = entities.create(
                "box",
                {"origin": [i, 0, 0], "dimensions": [1, 1, 1]},
            )
            entities.delete(entity_id)
        assert entities.count() == 0

    def test_many_documents_no_cross_talk(self) -> None:
        manager = DocumentManager()
        created = [manager.create(f"doc_{uuid.uuid4().hex[:6]}.json") for _ in range(200)]
        assert len(set(created)) == len(created)
        assert len(manager._session.active_files) == 200
