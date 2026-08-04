"""Transport layer: stdio, streamable HTTP and WebSocket collaboration sync.

The HTTP transport exposes ``/health`` and ``/metrics`` custom routes and
applies API-key authentication plus sliding-window rate limiting via
Starlette middleware. The MCP endpoint itself lives at ``/mcp``.

The WebSocket transport is a **collaboration sync channel** (the ``mcp``
SDK has no native WS transport): clients subscribe to a
:class:`~tianshangcad.core.collab.CollabSession`, push CRDT operations
and receive broadcast deltas. It reuses ``cad_collab_sync`` and the
``[collab]`` extra's ``websockets`` dependency, so it is optional.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from mcp.server import MCPServer

from tianshangcad.mcp.auth import api_key_enabled, validate_api_key
from tianshangcad.mcp.collab_hub import CollabHub
from tianshangcad.mcp.rate_limit import RateLimiter
from tianshangcad.utils.config import get_settings


class WebSocketLike(Protocol):
    """Minimal async WebSocket surface used by the sync handler."""

    async def accept(self) -> None:
        """Accept the incoming connection."""

    async def send(self, payload: str) -> None:
        """Send a text frame."""

    async def receive(self) -> str | None:
        """Receive the next text frame (``None`` when closed)."""


def run_stdio(server: MCPServer) -> None:
    """Run the server over stdio (default for local AI agents)."""
    asyncio.run(server.run_stdio_async())


def _register_http_routes(server: MCPServer) -> None:
    """Register the health and metrics custom routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from tianshangcad.utils.metrics import metrics_endpoint

    @server.custom_route("/health", methods=["GET"], name="health")  # type: ignore[untyped-decorator]
    async def health_endpoint(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "tianshangcad-server"})

    @server.custom_route("/metrics", methods=["GET"], name="metrics")  # type: ignore[untyped-decorator]
    async def metrics_endpoint_route(request: Request) -> object:
        return metrics_endpoint(request)


def _client_id(request: object) -> str:
    """Derive a stable client id from the request."""
    headers = getattr(request, "headers", None)
    if headers is not None:
        xfwd = headers.get("x-forwarded-for")
        if xfwd:
            return str(xfwd).split(",")[0].strip()
    client = getattr(request, "client", None)
    if client is not None:
        host = getattr(client, "host", None)
        if host:
            return str(host)
    return "unknown"


def _build_middleware(app: object) -> object:
    """Wrap the Starlette app with auth and rate-limiting middleware."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    settings = get_settings()
    auth_guard = api_key_enabled()
    limiter = RateLimiter(
        max_requests=settings.rate_limit_max,
        window_seconds=settings.rate_limit_window,
    )

    class _AuthMiddleware(BaseHTTPMiddleware):
        """Reject unauthenticated requests when an API key is configured."""

        async def dispatch(self, request, call_next):  # type: ignore[no-untyped-def]
            path = request.url.path
            # Public endpoints are excluded from authentication.
            if path in ("/health", "/metrics"):
                return await call_next(request)
            if not auth_guard:
                return await call_next(request)
            token = request.headers.get("x-api-key") or request.headers.get(
                "authorization"
            )
            if isinstance(token, str) and token.lower().startswith("bearer "):
                token = token[7:]
            if not validate_api_key(token):
                if token is None or not token:
                    return JSONResponse(
                        {"error": "Missing API key", "code": "missing_api_key"},
                        status_code=401,
                    )
                return JSONResponse(
                    {"error": "Invalid API key", "code": "invalid_api_key"},
                    status_code=403,
                )
            return await call_next(request)

    class _RateLimitMiddleware(BaseHTTPMiddleware):
        """Sliding-window rate limiting per client."""

        async def dispatch(self, request, call_next):  # type: ignore[no-untyped-def]
            path = request.url.path
            if path in ("/health", "/metrics"):
                return await call_next(request)
            client = _client_id(request)
            if not limiter.is_allowed(client):
                return JSONResponse(
                    {
                        "error": "Rate limit exceeded",
                        "code": "rate_limited",
                        "retry_after_seconds": settings.rate_limit_window,
                    },
                    status_code=429,
                    headers={"Retry-After": str(settings.rate_limit_window)},
                )
            return await call_next(request)

    app.add_middleware(_AuthMiddleware)  # type: ignore[attr-defined]
    app.add_middleware(_RateLimitMiddleware)  # type: ignore[attr-defined]
    return app


def build_http_app(
    server: MCPServer,
    streamable_http_path: str = "/mcp",
    host: str = "127.0.0.1",
) -> Any:
    """Build the streamable HTTP Starlette app with auth + metrics routes.

    Returns the Starlette ASGI app instance. Extracted from :func:`run_http`
    so integration tests can exercise the real HTTP stack (init, middleware,
    call) over ``httpx.ASGITransport`` or a live uvicorn server.
    """
    _register_http_routes(server)
    app = server.streamable_http_app(
        streamable_http_path=streamable_http_path,
        host=host,
    )
    _build_middleware(app)
    return app


def run_http(
    server: MCPServer,
    host: str = "127.0.0.1",
    port: int = 8081,
    streamable_http_path: str = "/mcp",
) -> None:
    """Run the server over streamable HTTP with auth + metrics routes."""
    app = build_http_app(server, streamable_http_path=streamable_http_path, host=host)
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")


# ---------------------------------------------------------------------------
# WebSocket collaboration sync
# ---------------------------------------------------------------------------


async def handle_ws_connection(
    websocket: WebSocketLike,
    *,
    on_sync: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    hub: CollabHub | None = None,
) -> None:
    """Serve one WebSocket client.

    The protocol is a small JSON envelope over the MCP sync tool:
    ``{"type": "subscribe", "session_id": ...}``,
    ``{"type": "op", "session_id": ..., "ops": [...], "by_user": ...}`` and
    ``{"type": "sync", "session_id": ..., "since": 0}``. The server replies
    with ``{"type": "deltas", ...}`` and, when a ``hub`` is provided,
    broadcasts applied ops to every other subscriber of the same session.
    ``on_sync`` defaults to a live ``cad_collab_sync`` wrapper; tests inject
    a stub.

    Outgoing frames always go through a single per-connection writer task
    that drains an ``asyncio.Queue``, so concurrent broadcasts never
    interleave on the socket.
    """
    outbox: asyncio.Queue[str] = asyncio.Queue()
    subscription: str | None = None

    async def _send(payload: dict[str, Any]) -> None:
        outbox.put_nowait(json.dumps(payload))

    async def _drain() -> None:
        while True:
            frame = await outbox.get()
            try:
                await websocket.send(frame)
            finally:
                outbox.task_done()

    async def _receive() -> dict[str, Any] | None:
        receive = getattr(websocket, "receive", None) or getattr(websocket, "recv", None)
        if receive is None:
            return None
        try:
            message = await receive()
        except Exception:
            return None
        if message is None:
            return None
        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    accept = getattr(websocket, "accept", None)
    if accept is not None:
        await accept()
    if on_sync is None:
        from tianshangcad.mcp.tools.collab import (
            CollabSyncInput,
            cad_collab_sync,
        )

        def on_sync(payload: dict[str, Any]) -> dict[str, Any]:
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

    writer = asyncio.create_task(_drain())
    try:
        while True:
            data = await _receive()
            if data is None:
                break
            kind = data.get("type")
            if kind == "subscribe":
                session_id = str(data.get("session_id", ""))
                if subscription is not None and hub is not None:
                    await hub.unsubscribe(subscription, outbox)
                subscription = session_id
                if hub is not None:
                    await hub.subscribe(session_id, outbox)
                await _send({"type": "subscribed", "session_id": session_id})
            elif kind == "op" or kind == "sync":
                session_id = str(data.get("session_id", subscription or ""))
                if not session_id:
                    await _send({"type": "error", "message": "session_id is required"})
                    continue
                try:
                    output = on_sync({**data, "session_id": session_id})
                except Exception as exc:
                    await _send({"type": "error", "message": str(exc)})
                    continue
                await _send({"type": "deltas", "session_id": session_id, **output})
                if kind == "op":
                    if hub is not None:
                        await hub.publish(
                            session_id,
                            {"type": "deltas", "session_id": session_id, **output},
                            exclude=outbox,
                        )
                    else:
                        await broadcast_deltas(session_id, output)
            elif kind == "ping":
                await _send({"type": "pong"})
            else:
                await _send({"type": "error", "message": f"Unknown message type: {kind}"})
    finally:
        if hub is not None and subscription is not None:
            await hub.unsubscribe(subscription, outbox)
        await outbox.join()
        writer.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await writer


async def broadcast_deltas(session_id: str, payload: dict[str, Any]) -> None:
    """Broadcast hook used when no :class:`CollabHub` is wired.

    The :func:`run_ws` path passes a real hub so applied ops fan out to every
    subscriber of the session; this fallback keeps
    :func:`handle_ws_connection` unit-testable without a live socket and is
    the extension point tests monkeypatch.
    """
    from tianshangcad.utils.logger import get_logger

    get_logger(__name__).info(
        "collab broadcast",
        session_id=session_id,
        ops=len(payload.get("ops", [])),
    )


def make_ws_connection_handler(
    hub: CollabHub,
    on_sync: Callable[[dict[str, Any]], dict[str, Any]],
) -> Callable[[WebSocketLike], Awaitable[None]]:
    """Return an async ``(websocket) -> None`` handler bound to ``hub``.

    Extracted so :func:`run_ws` and the integration tests share one wiring.
    """

    async def handler(websocket: WebSocketLike) -> None:
        await handle_ws_connection(websocket, on_sync=on_sync, hub=hub)

    return handler


def run_ws(host: str = "127.0.0.1", port: int = 8082) -> None:
    """Run a WebSocket collaboration hub on ``host:port``.

    Requires the optional ``[collab]`` extra (``websockets``). Each client
    is served by :func:`handle_ws_connection` through a shared
    :class:`CollabHub`, so an ``op`` from one client broadcasts deltas to
    every other subscriber of the same session.
    """
    try:
        import websockets  # type: ignore[import-not-found, unused-ignore]
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "WebSocket transport requires the 'collab' extra: pip install -e '.[collab]'"
        ) from exc

    def on_sync(payload: dict[str, Any]) -> dict[str, Any]:
        from tianshangcad.mcp.tools.collab import (
            CollabSyncInput,
            cad_collab_sync,
        )

        # Bind the payload to a concrete session if it exists, otherwise
        # let the sync tool raise the friendly "session_not_found" error.
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

    hub = CollabHub()
    handler = make_ws_connection_handler(hub, on_sync)

    async def serve() -> None:
        async with websockets.serve(handler, host, port):  # type: ignore[arg-type, unused-ignore]
            await asyncio.Future()  # run forever

    asyncio.run(serve())
