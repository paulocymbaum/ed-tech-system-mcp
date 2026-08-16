"""Debounce gate for outbound LLM provider calls."""

from __future__ import annotations

import asyncio
import threading
import time

from mcp_server.domain.llm_routing import ILLMDebounceGate, LLMComplexity

DEFAULT_DEBOUNCE_SECONDS = 0.1


class IntervalLLMDebounceGate(ILLMDebounceGate):
    """Enforce a minimum interval between consecutive calls of the same complexity."""

    def __init__(self, interval_seconds: float = DEFAULT_DEBOUNCE_SECONDS) -> None:
        if interval_seconds < 0:
            msg = "interval_seconds must be non-negative"
            raise ValueError(msg)
        self._interval_seconds = interval_seconds
        self._sync_lock = threading.Lock()
        self._async_locks: dict[LLMComplexity, asyncio.Lock] = {}
        self._last_call_monotonic: dict[LLMComplexity, float] = {}

    def _ensure_async_lock(self, complexity: LLMComplexity) -> asyncio.Lock:
        lock = self._async_locks.get(complexity)
        if lock is None:
            with self._sync_lock:
                lock = self._async_locks.get(complexity)
                if lock is None:
                    lock = asyncio.Lock()
                    self._async_locks[complexity] = lock
        return lock

    def acquire_sync(self, complexity: LLMComplexity = LLMComplexity.MEDIUM) -> None:
        if self._interval_seconds == 0:
            return
        with self._sync_lock:
            self._wait_for_interval_sync(complexity)

    async def acquire(self, complexity: LLMComplexity = LLMComplexity.MEDIUM) -> None:
        if self._interval_seconds == 0:
            return
        async with self._ensure_async_lock(complexity):
            now = time.monotonic()
            elapsed = now - self._last_call_monotonic.get(complexity, 0.0)
            if elapsed < self._interval_seconds:
                await asyncio.sleep(self._interval_seconds - elapsed)
            self._last_call_monotonic[complexity] = time.monotonic()

    def _wait_for_interval_sync(self, complexity: LLMComplexity) -> None:
        if self._interval_seconds == 0:
            return
        now = time.monotonic()
        elapsed = now - self._last_call_monotonic.get(complexity, 0.0)
        if elapsed < self._interval_seconds:
            time.sleep(self._interval_seconds - elapsed)
        self._last_call_monotonic[complexity] = time.monotonic()
