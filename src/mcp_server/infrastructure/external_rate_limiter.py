"""Sliding-window rate limiter for outbound external API calls."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque

from mcp_server.domain.exceptions import ExternalRateLimitError
from mcp_server.domain.external_rate_limit import (
    EXTERNAL_RATE_LIMIT_MESSAGE,
    IExternalRequestRateLimiter,
)


class SlidingWindowExternalRequestRateLimiter(IExternalRequestRateLimiter):
    """Enforce a shared per-minute cap across all external providers."""

    def __init__(self, limit_per_minute: int, *, window_seconds: float = 60.0) -> None:
        if limit_per_minute <= 0:
            msg = "limit_per_minute must be positive"
            raise ValueError(msg)
        self._limit_per_minute = limit_per_minute
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    def acquire_sync(self, *, provider: str) -> None:
        del provider
        with self._sync_lock:
            self._reserve_or_raise()

    async def acquire(self, *, provider: str) -> None:
        del provider
        async with self._async_lock:
            self._reserve_or_raise()

    def _reserve_or_raise(self) -> None:
        now = time.monotonic()
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()
        if len(self._timestamps) >= self._limit_per_minute:
            raise ExternalRateLimitError(EXTERNAL_RATE_LIMIT_MESSAGE)
        self._timestamps.append(now)
