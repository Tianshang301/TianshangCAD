"""End-to-end WebSocket integration tests (requires the ``[collab]`` extra).

These tests exercise the real ``websockets`` server loop wired through
:func:`tianshangcad.mcp.transport.make_ws_connection_handler` and a shared
:class:`CollabHub`. They are skipped when ``websockets`` is not installed
(``pip install -e ".[collab]"``).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import pytest

websockets = pytest.importorskip("websockets")

from tianshangcad.core.collab import CollabManager  # noqa: E402
from tianshangcad.mcp.collab_hub import CollabHub  # noqa: E402
from tianshangcad.mcp.transport import make_ws_connection_handler  # noqa: E402


def _make_ws_on_sync() -> Callable[[dict], dict]:
    from tianshangcad.mcp.tools.collab import (
        CollabSyncInput,
        cad_collab_sync,
    )

    def on_sync(payload: dict) -> dict:
        result = cad_collab_sync(
            CollabSyncInput(
                session_id=str(payload["session_id"]),
                since=int(payload.get("since", 0)),
                ops=list(payload.get("ops", [])),
                include_state=bool(payload.get("include_state", True)),
                by_user=str(payload.get("by_user", "owner")),
            )
        )
        return result.model_dump()

    return on_sync


async def _recv(ws, timeout: float = 3.0) -> dict:
    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
    return json.loads(raw)


async def _serve(handler, host: str = "127.0.0.1"):
    server = await websockets.serve(handler, host, 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


def test_real_ws_two_clients_broadcast() -> None:
    async def scenario() -> None:
        manager = CollabManager()
        manager.reset()
        session = manager.create_session("d1", name="live", owner="owner")
        hub = CollabHub()
        handler = make_ws_connection_handler(hub, _make_ws_on_sync())
        server, port = await _serve(handler)
        try:
            alice = await websockets.connect(f"ws://127.0.0.1:{port}")
            bob = await websockets.connect(f"ws://127.0.0.1:{port}")
            try:
                await alice.send(
                    json.dumps({"type": "subscribe", "session_id": session.session_id})
                )
                assert (await _recv(alice))["type"] == "subscribed"
                await bob.send(
                    json.dumps({"type": "subscribe", "session_id": session.session_id})
                )
                assert (await _recv(bob))["type"] == "subscribed"
                assert hub.subscriber_count(session.session_id) == 2

                await alice.send(
                    json.dumps(
                        {
                            "type": "op",
                            "session_id": session.session_id,
                            "ops": [{"key": "k", "value": 1}],
                        }
                    )
                )
                own = await _recv(alice)
                assert own["type"] == "deltas"
                broadcast = await _recv(bob)
                assert broadcast["type"] == "deltas"
                assert broadcast["status"] == "success"
                assert broadcast["applied"][0]["key"] == "k"
                assert broadcast["applied"][0]["value"] == 1
            finally:
                await alice.close()
                await bob.close()
        finally:
            server.close()
            await server.wait_closed()
        # Both connections gone -> the hub registry is empty.
        assert hub.subscriber_count(session.session_id) == 0
        manager.reset()

    asyncio.run(scenario())


def test_real_ws_ping_and_sync() -> None:
    async def scenario() -> None:
        manager = CollabManager()
        manager.reset()
        session = manager.create_session("d1", name="live", owner="owner")
        hub = CollabHub()
        handler = make_ws_connection_handler(hub, _make_ws_on_sync())
        server, port = await _serve(handler)
        try:
            client = await websockets.connect(f"ws://127.0.0.1:{port}")
            try:
                await client.send(json.dumps({"type": "ping"}))
                assert (await _recv(client)) == {"type": "pong"}

                await client.send(
                    json.dumps({"type": "sync", "session_id": session.session_id, "since": 0})
                )
                reply = await _recv(client)
                assert reply["type"] == "deltas"
                assert reply["status"] == "success"
            finally:
                await client.close()
        finally:
            server.close()
            await server.wait_closed()
        manager.reset()

    asyncio.run(scenario())


def test_real_ws_unknown_message_errors() -> None:
    async def scenario() -> None:
        hub = CollabHub()
        handler = make_ws_connection_handler(hub, _make_ws_on_sync())
        server, port = await _serve(handler)
        try:
            client = await websockets.connect(f"ws://127.0.0.1:{port}")
            try:
                await client.send(json.dumps({"type": "explode"}))
                reply = await _recv(client)
                assert reply["type"] == "error"
                assert "Unknown message type" in reply["message"]
            finally:
                await client.close()
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())


def test_real_ws_op_on_real_session_updates_state() -> None:
    async def scenario() -> None:
        manager = CollabManager()
        manager.reset()
        session = manager.create_session("d1", name="live", owner="owner")
        hub = CollabHub()
        handler = make_ws_connection_handler(hub, _make_ws_on_sync())
        server, port = await _serve(handler)
        try:
            client = await websockets.connect(f"ws://127.0.0.1:{port}")
            try:
                await client.send(
                    json.dumps({"type": "subscribe", "session_id": session.session_id})
                )
                assert (await _recv(client))["type"] == "subscribed"

                await client.send(
                    json.dumps(
                        {
                            "type": "op",
                            "session_id": session.session_id,
                            "ops": [{"key": "entity:e1", "value": {"r": 1}}],
                        }
                    )
                )
                reply = await _recv(client)
                assert reply["type"] == "deltas"
                assert reply["status"] == "success"
                assert session.state_dict()["entity:e1"] == {"r": 1}
            finally:
                await client.close()
        finally:
            server.close()
            await server.wait_closed()
        manager.reset()

    asyncio.run(scenario())
