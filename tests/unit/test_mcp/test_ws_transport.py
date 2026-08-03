"""WebSocket transport unit tests using a stub socket."""

from __future__ import annotations

import asyncio
import json

from cad_mcp_server.mcp import transport
from cad_mcp_server.mcp.transport import handle_ws_connection


class StubWebSocket:
    """Fake async WebSocket that records what it sends."""

    def __init__(self, messages: list[dict]) -> None:
        self._inbox: list[str | None] = [json.dumps(m) for m in messages]
        self.sent: list[dict] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def receive(self) -> str | None:
        return self._inbox.pop(0) if self._inbox else None


def _run(messages: list[dict], on_sync, **kwargs):
    sock = StubWebSocket(messages)
    asyncio.run(handle_ws_connection(sock, on_sync=on_sync, **kwargs))
    return sock


def test_ws_subscribe_then_sync() -> None:
    sock = _run(
        [
            {"type": "subscribe", "session_id": "s1"},
            {"type": "sync", "session_id": "s1", "since": 0},
            {"type": "ping"},
        ],
        on_sync=lambda payload: {
            "session_id": payload["session_id"],
            "applied": [],
            "deltas": [{"seq": 1, "key": "k", "value": 1}],
            "state": {"k": 1},
            "status": "success",
        },
    )
    assert sock.accepted is True
    assert sock.sent[0] == {"type": "subscribed", "session_id": "s1"}
    assert sock.sent[1]["type"] == "deltas"
    assert sock.sent[1]["state"] == {"k": 1}
    assert sock.sent[-1] == {"type": "pong"}


def test_ws_op_calls_broadcast(monkeypatch) -> None:
    broadcast_calls: list[tuple[str, dict]] = []

    async def fake_broadcast(session_id: str, payload: dict) -> None:
        broadcast_calls.append((session_id, payload))

    monkeypatch.setattr(transport, "broadcast_deltas", fake_broadcast)

    def on_sync(payload: dict) -> dict:
        return {"session_id": "s1", "applied": [payload["ops"]], "deltas": [], "state": {}}

    sock = _run([{"type": "op", "session_id": "s1", "ops": [{"key": "k", "value": 2}]}], on_sync)
    assert sock.sent[0]["type"] == "deltas"
    assert broadcast_calls[0][0] == "s1"
    assert broadcast_calls[0][1]["applied"] == [[{"key": "k", "value": 2}]]


def test_ws_error_on_missing_session() -> None:
    def on_sync(payload: dict) -> dict:
        raise AssertionError("should not be called")

    sock = _run([{"type": "sync"}], on_sync)
    assert sock.sent[0]["type"] == "error"
    assert "session_id is required" in sock.sent[0]["message"]


def test_ws_error_when_sync_raises() -> None:
    def on_sync(payload: dict) -> dict:
        raise RuntimeError("boom")

    sock = _run([{"type": "sync", "session_id": "s1"}], on_sync)
    assert sock.sent[0]["type"] == "error"
    assert "boom" in sock.sent[0]["message"]


def test_ws_unknown_message() -> None:
    sock = _run([{"type": "explode"}], lambda payload: {})
    assert sock.sent[0]["type"] == "error"
    assert "Unknown message type" in sock.sent[0]["message"]


def test_ws_closes_on_no_messages() -> None:
    sock = _run([], lambda payload: {})
    assert sock.accepted is True
    assert sock.sent == []
