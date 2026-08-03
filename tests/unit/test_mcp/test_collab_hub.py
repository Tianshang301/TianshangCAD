"""CollabHub subscription / fan-out unit tests."""

from __future__ import annotations

import asyncio
import json

from cad_mcp_server.mcp.collab_hub import CollabHub


def _run(coro):
    return asyncio.run(coro)


class TestCollabHub:
    """Subscribe / unsubscribe / publish semantics."""

    def test_publish_delivers_json_to_all_subscribers(self) -> None:
        async def scenario() -> None:
            hub = CollabHub()
            qa: asyncio.Queue[str] = asyncio.Queue()
            qb: asyncio.Queue[str] = asyncio.Queue()
            await hub.subscribe("s1", qa)
            await hub.subscribe("s1", qb)

            delivered = await hub.publish("s1", {"type": "deltas", "k": 1})
            assert delivered == 2
            assert json.loads(qa.get_nowait()) == {"type": "deltas", "k": 1}
            assert json.loads(qb.get_nowait()) == {"type": "deltas", "k": 1}

        _run(scenario())

    def test_publish_exclude_skips_origin(self) -> None:
        async def scenario() -> None:
            hub = CollabHub()
            origin: asyncio.Queue[str] = asyncio.Queue()
            peer: asyncio.Queue[str] = asyncio.Queue()
            await hub.subscribe("s1", origin)
            await hub.subscribe("s1", peer)

            delivered = await hub.publish("s1", {"type": "deltas", "k": 1}, exclude=origin)
            assert delivered == 1
            assert origin.empty()
            assert json.loads(peer.get_nowait())["k"] == 1

        _run(scenario())

    def test_unsubscribe_removes_and_drops_empty_bucket(self) -> None:
        async def scenario() -> None:
            hub = CollabHub()
            qa: asyncio.Queue[str] = asyncio.Queue()
            qb: asyncio.Queue[str] = asyncio.Queue()
            await hub.subscribe("s1", qa)
            await hub.subscribe("s1", qb)
            await hub.unsubscribe("s1", qa)
            assert hub.subscriber_count("s1") == 1

            await hub.unsubscribe("s1", qb)
            assert hub.subscriber_count("s1") == 0
            assert hub.session_ids() == []

        _run(scenario())

    def test_unsubscribe_unknown_session_is_noop(self) -> None:
        async def scenario() -> None:
            hub = CollabHub()
            q: asyncio.Queue[str] = asyncio.Queue()
            await hub.unsubscribe("nope", q)
            assert hub.session_ids() == []

        _run(scenario())

    def test_publish_unknown_session(self) -> None:
        async def scenario() -> None:
            hub = CollabHub()
            delivered = await hub.publish("nope", {"type": "deltas"})
            assert delivered == 0

        _run(scenario())

    def test_session_ids_lists_active_sessions(self) -> None:
        async def scenario() -> None:
            hub = CollabHub()
            q1: asyncio.Queue[str] = asyncio.Queue()
            q2: asyncio.Queue[str] = asyncio.Queue()
            await hub.subscribe("s1", q1)
            await hub.subscribe("s2", q2)
            assert set(hub.session_ids()) == {"s1", "s2"}

        _run(scenario())
