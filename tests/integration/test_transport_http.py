"""HTTP transport integration tests over a live uvicorn server.

Exercises the real streamable-HTTP stack (initialize / list / call), the
``/health`` route and API-key auth, using the official MCP HTTP client plus
``httpx`` for the plain routes.
"""

from __future__ import annotations

import os
import threading
import time

import httpx
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from tianshangcad.mcp.server import build_server
from tianshangcad.mcp.transport import build_http_app


def _serve(app: object, *, url_path: str = "/mcp") -> tuple[uvicorn.Server, threading.Thread, str]:
    """Start the app on an ephemeral port; return (server, thread, base_url)."""
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started and server.servers:
            break
        time.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    return server, thread, f"http://127.0.0.1:{port}{url_path}"


def _stop(server: uvicorn.Server, thread: threading.Thread) -> None:
    server.should_exit = True
    thread.join(timeout=10)


class TestHTTPTransport:
    """End-to-end HTTP streamable MCP transport tests."""

    def test_full_roundtrip(self) -> None:
        app = build_http_app(build_server())
        server, thread, url = _serve(app)
        try:
            async def run() -> tuple[int, str, bool]:
                async with (
                    streamable_http_client(url) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    tools = await session.list_tools()
                    names = [tool.name for tool in tools.tools]
                    result = await session.call_tool("cad_metrics_get", {})
                    return (
                        len(tools.tools),
                        result.content[0].text[:80],
                        "cad_file_create" in names,
                    )

            import asyncio

            count, text, has_create = asyncio.run(run())
            assert count == 103
            assert has_create
            assert '"files": 0' in text
        finally:
            _stop(server, thread)

    def test_health_endpoint(self) -> None:
        app = build_http_app(build_server())
        server, thread, url = _serve(app)
        try:
            response = httpx.get(url.removesuffix("/mcp") + "/health", timeout=10)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
        finally:
            _stop(server, thread)

    def test_api_key_authentication(self) -> None:
        os.environ["TIANGSHANGCAD_API_KEY"] = "http-secret"
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            app = build_http_app(build_server())
            server, thread, url = _serve(app)
            try:
                base = url.removesuffix("/mcp")
                missing = httpx.post(
                    url, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, timeout=10
                )
                assert missing.status_code == 401
                with_key = httpx.post(
                    url,
                    json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                    headers={"x-api-key": "http-secret"},
                    timeout=10,
                )
                assert with_key.status_code != 401
                assert httpx.get(base + "/health", timeout=10).status_code == 200
            finally:
                _stop(server, thread)
        finally:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            os.environ.pop("TIANGSHANGCAD_API_KEY", None)
