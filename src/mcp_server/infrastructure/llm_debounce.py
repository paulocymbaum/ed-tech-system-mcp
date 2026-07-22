"""Debounce gate for outbound LLM provider calls."""

from __future__ import annotations

import asyncio
import threading
import time

from mcp_server.domain.llm_routing import ILLMDebounceGate

DEFAULT_DEBOUNCE_SECONDS = 0.1


class IntervalLLMDebounceGate(ILLMDebounceGate):
    """Enforce a minimum interval between consecutive provider calls."""

    def __init__(self, interval_seconds: float = DEFAULT_DEBOUNCE_SECONDS) -> None:
        if interval_seconds < 0:
            msg = "interval_seconds must be non-negative"
            raise ValueError(msg)
        self._interval_seconds = interval_seconds
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()
        self._last_call_monotonic = 0.0

    def acquire_sync(self) -> None:
        with self._sync_lock:
            self._wait_for_interval_sync()

    async def acquire(self) -> None:
        if self._interval_seconds == 0:
            return
        async with self._async_lock:
            now = time.monotonic()
            elapsed = now - self._last_call_monotonic
            if elapsed < self._interval_seconds:
                await asyncio.sleep(self._interval_seconds - elapsed)
            self._last_call_monotonic = time.monotonic()

    def _wait_for_interval_sync(self) -> None:
        if self._interval_seconds == 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_call_monotonic
        if elapsed < self._interval_seconds:
            time.sleep(self._interval_seconds - elapsed)
        self._last_call_monotonic = time.monotonic()


DebounceGate = IntervalLLMDebounceGate
