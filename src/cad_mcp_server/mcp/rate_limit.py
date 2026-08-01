"""Sliding-window rate limiting for the HTTP transport.

Each client (identified by a header / IP) is limited to ``max_requests``
requests per ``window_seconds``. Thread-safe via a lock.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from cad_mcp_server.utils.errors import RateLimitError


class RateLimiter:
    """Simple sliding-window rate limiter keyed by client id."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        """Initialize the limiter with the given limits."""
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_id: str) -> bool:
        """Record a request for ``client_id`` and return whether it may proceed."""
        now = time.time()
        with self._lock:
            timestamps = self._requests[client_id]
            cutoff = now - self.window
            self._requests[client_id] = [t for t in timestamps if t > cutoff]
            if len(self._requests[client_id]) >= self.max_requests:
                return False
            self._requests[client_id].append(now)
            return True

    def check(self, client_id: str) -> None:
        """Raise ``RateLimitError`` when ``client_id`` is over the limit."""
        if not self.is_allowed(client_id):
            raise RateLimitError(
                f"Rate limit exceeded ({self.max_requests} requests per "
                f"{self.window}s); retry later",
                code="rate_limited",
            )

    def remaining(self, client_id: str) -> int:
        """Return the number of requests still allowed for ``client_id``."""
        now = time.time()
        with self._lock:
            timestamps = self._requests.get(client_id, [])
            cutoff = now - self.window
            active = [t for t in timestamps if t > cutoff]
            return max(0, self.max_requests - len(active))
