"""API-key authentication for the HTTP transport.

A single ``CAD_API_KEY`` (or a comma-separated ``TIANSHANGCAD_API_KEYS`` list)
guards the MCP streamable HTTP endpoint. stdio mode is unaffected. When
no key is configured the HTTP endpoint is open (local development).
"""

from __future__ import annotations

import hmac

from tianshangcad.utils.config import get_settings


def _configured_keys() -> list[str]:
    """Return the list of valid API keys from settings."""
    settings = get_settings()
    keys: list[str] = []
    for raw in (settings.api_key, settings.api_keys):
        for part in str(raw or "").split(","):
            token = part.strip()
            if token:
                keys.append(token)
    return keys


def api_key_enabled() -> bool:
    """Return whether API-key authentication is configured."""
    return bool(_configured_keys())


def validate_api_key(token: str | None) -> bool:
    """Return whether ``token`` is a valid API key.

    When no keys are configured the endpoint is open and any request is
    allowed (returns ``True``).
    """
    if not api_key_enabled():
        return True
    if not token:
        return False
    candidate = token.strip()
    return any(
        hmac.compare_digest(candidate.encode(), key.encode()) for key in _configured_keys()
    )
