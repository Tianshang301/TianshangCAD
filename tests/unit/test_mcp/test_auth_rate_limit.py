"""Tests for API-key auth and rate limiting on the HTTP transport."""

from __future__ import annotations

import os

# Force env prefix initialization before any tianshangcad imports
os.environ.setdefault("TIANSHANGCAD_API_KEY", "")

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from tianshangcad.mcp.auth import api_key_enabled, validate_api_key
from tianshangcad.mcp.rate_limit import RateLimiter
from tianshangcad.mcp.transport import _build_middleware
from tianshangcad.utils.errors import RateLimitError


def _app() -> Starlette:
    app = Starlette(routes=[])

    async def ok(request) -> JSONResponse:
        return JSONResponse({"ok": True})

    app.add_route("/test", ok, methods=["GET"])
    return app


class TestAuth:
    """API-key authentication helpers and middleware."""

    def test_disabled_when_no_key(self) -> None:
        old = os.environ.get("TIANSHANGCAD_API_KEY")
        os.environ["TIANSHANGCAD_API_KEY"] = ""
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            assert api_key_enabled() is False
            assert validate_api_key(None) is True
        finally:
            get_settings.cache_clear()
            if old is None:
                os.environ.pop("TIANSHANGCAD_API_KEY", None)
            else:
                os.environ["TIANSHANGCAD_API_KEY"] = old

    def test_enabled_with_key(self) -> None:
        os.environ["TIANSHANGCAD_API_KEY"] = "secret123"
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            assert api_key_enabled() is True
            assert validate_api_key("secret123") is True
            assert validate_api_key("wrong") is False
            assert validate_api_key(None) is False
        finally:
            get_settings.cache_clear()
            os.environ.pop("TIANSHANGCAD_API_KEY", None)

    def test_multiple_keys(self) -> None:
        os.environ["TIANSHANGCAD_API_KEYS"] = "k1,k2,k3"
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            assert validate_api_key("k2") is True
            assert validate_api_key("k4") is False
        finally:
            get_settings.cache_clear()
            os.environ.pop("TIANSHANGCAD_API_KEYS", None)

    def test_constant_time_comparison(self) -> None:
        os.environ["TIANSHANGCAD_API_KEY"] = "secret123"
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            assert validate_api_key(" secret123 ") is True
            assert validate_api_key("SECRET123") is False
            assert validate_api_key("") is False
        finally:
            get_settings.cache_clear()
            os.environ.pop("TIANSHANGCAD_API_KEY", None)

    def test_middleware_rejects_without_key(self) -> None:
        os.environ["TIANSHANGCAD_API_KEY"] = "secret123"
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            client = TestClient(_build_middleware(_app()))
            response = client.get("/test")
            assert response.status_code == 401
        finally:
            get_settings.cache_clear()
            os.environ.pop("TIANSHANGCAD_API_KEY", None)

    def test_middleware_rejects_wrong_key(self) -> None:
        os.environ["TIANSHANGCAD_API_KEY"] = "secret123"
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            client = TestClient(_build_middleware(_app()))
            response = client.get("/test", headers={"x-api-key": "wrong"})
            assert response.status_code == 403
        finally:
            get_settings.cache_clear()
            os.environ.pop("TIANSHANGCAD_API_KEY", None)

    def test_middleware_accepts_correct_key(self) -> None:
        os.environ["TIANSHANGCAD_API_KEY"] = "secret123"
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            client = TestClient(_build_middleware(_app()))
            response = client.get("/test", headers={"x-api-key": "secret123"})
            assert response.status_code == 200
        finally:
            get_settings.cache_clear()
            os.environ.pop("TIANSHANGCAD_API_KEY", None)

    def test_middleware_accepts_bearer_token(self) -> None:
        os.environ["TIANSHANGCAD_API_KEY"] = "secret123"
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            client = TestClient(_build_middleware(_app()))
            response = client.get("/test", headers={"authorization": "Bearer secret123"})
            assert response.status_code == 200
        finally:
            get_settings.cache_clear()
            os.environ.pop("TIANSHANGCAD_API_KEY", None)


class TestRateLimiter:
    """Sliding-window rate limiter."""

    def test_allows_under_limit(self) -> None:
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert limiter.is_allowed("client-a") is True

    def test_blocks_over_limit(self) -> None:
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed("client-a") is True
        assert limiter.is_allowed("client-a") is True
        assert limiter.is_allowed("client-a") is False

    def test_clients_are_independent(self) -> None:
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.is_allowed("a") is True
        assert limiter.is_allowed("b") is True
        assert limiter.is_allowed("a") is False

    def test_check_raises(self) -> None:
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.check("client-a")
        with pytest.raises(RateLimitError):
            limiter.check("client-a")

    def test_remaining(self) -> None:
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        limiter.check("client-a")
        assert limiter.remaining("client-a") == 2

    def test_middleware_returns_429(self) -> None:
        os.environ["TIANSHANGCAD_RATE_LIMIT_MAX"] = "2"
        os.environ["TIANSHANGCAD_RATE_LIMIT_WINDOW"] = "60"
        os.environ["TIANSHANGCAD_API_KEY"] = ""
        try:
            from tianshangcad.utils.config import get_settings

            get_settings.cache_clear()
            client = TestClient(_build_middleware(_app()))
            assert client.get("/test").status_code == 200
            assert client.get("/test").status_code == 200
            assert client.get("/test").status_code == 429
        finally:
            get_settings.cache_clear()
            os.environ.pop("TIANSHANGCAD_RATE_LIMIT_MAX", None)
            os.environ.pop("TIANSHANGCAD_RATE_LIMIT_WINDOW", None)
            os.environ.pop("TIANSHANGCAD_API_KEY", None)
