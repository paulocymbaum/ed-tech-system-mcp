"""Keyed sliding-window limiter for inbound MCP tools/call."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict, deque

from mcp_server.domain.exceptions import ExternalRateLimitError
from mcp_server.domain.inbound_rate_limit import (
    INBOUND_RATE_LIMIT_MESSAGE,
    IInboundToolRateLimiter,
)


class KeyedSlidingWindowInboundRateLimiter(IInboundToolRateLimiter):
    """Per-caller sliding window; quota keys must already be hashed."""

    def __init__(self, limit_per_minute: int, *, window_seconds: float = 60.0) -> None:
        if limit_per_minute <= 0:
            msg = "limit_per_minute must be positive"
            raise ValueError(msg)
        self._limit_per_minute = limit_per_minute
        self._window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._sync_lock = threading.Lock()
        self._async_lock: asyncio.Lock | None = None

    def _ensure_async_lock(self) -> asyncio.Lock:
        if self._async_lock is None:
            with self._sync_lock:
                if self._async_lock is None:
                    self._async_lock = asyncio.Lock()
        return self._async_lock

    async def acquire(self, *, quota_key: str) -> None:
        async with self._ensure_async_lock():
            now = time.monotonic()
            cutoff = now - self._window_seconds
            window = self._windows[quota_key]
            while window and window[0] <= cutoff:
                window.popleft()
            if len(window) >= self._limit_per_minute:
                raise ExternalRateLimitError(INBOUND_RATE_LIMIT_MESSAGE)
            window.append(now)
