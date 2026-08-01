"""Transport layer: stdio and streamable HTTP.

The HTTP transport exposes ``/health`` and ``/metrics`` custom routes and
applies API-key authentication plus sliding-window rate limiting via
Starlette middleware. The MCP endpoint itself lives at ``/mcp``.
"""

from __future__ import annotations

import asyncio

from mcp.server import MCPServer

from cad_mcp_server.mcp.auth import api_key_enabled, validate_api_key
from cad_mcp_server.mcp.rate_limit import RateLimiter
from cad_mcp_server.utils.config import get_settings


def run_stdio(server: MCPServer) -> None:
    """Run the server over stdio (default for local AI agents)."""
    asyncio.run(server.run_stdio_async())


def _register_http_routes(server: MCPServer) -> None:
    """Register the health and metrics custom routes."""
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    from cad_mcp_server.utils.metrics import metrics_endpoint

    @server.custom_route("/health", methods=["GET"], name="health")  # type: ignore[untyped-decorator]
    async def health_endpoint(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "cad-mcp-server"})

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


def run_http(
    server: MCPServer,
    host: str = "127.0.0.1",
    port: int = 8081,
    streamable_http_path: str = "/mcp",
) -> None:
    """Run the server over streamable HTTP with auth + metrics routes."""
    _register_http_routes(server)
    app = server.streamable_http_app(
        streamable_http_path=streamable_http_path,
        host=host,
    )
    _build_middleware(app)
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
