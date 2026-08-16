"""Cache-aside helper with per-key singleflight (stampede protection).

``CacheAsideCoordinator`` keeps one ``asyncio.Lock`` per cache key during miss
paths so concurrent requests for the same key invoke the inner port at most once.
Lock entries are removed when the lock is released and no longer held. When the
in-process lock map exceeds ``max_locks`` (default 1024), it is cleared to bound
memory; keys are recreated on demand.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from mcp_server.domain.cache import CacheRule, ICacheStore
from mcp_server.infrastructure.cache_observability import record_cache_hit, record_cache_miss
from mcp_server.infrastructure.cache_serialization import payload_within_cache_limit
from mcp_server.infrastructure.port_observability import PortCallSpan


class CacheAsideCoordinator:
    """Per-key singleflight locks for cache-aside miss coalescing."""

    def __init__(self, *, max_locks: int = 1024) -> None:
        self._locks: OrderedDict[str, asyncio.Lock] = OrderedDict()
        self._max_locks = max_locks

    def _evict_idle(self) -> None:
        if len(self._locks) < self._max_locks:
            return
        for key, lock in list(self._locks.items()):
            if not lock.locked():
                self._locks.pop(key, None)
            if len(self._locks) < self._max_locks:
                return

    @asynccontextmanager
    async def singleflight(self, key: str) -> AsyncIterator[None]:
        self._evict_idle()
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        else:
            self._locks.move_to_end(key)
        try:
            async with lock:
                yield
        finally:
            if not lock.locked():
                self._locks.pop(key, None)


_coordinator = CacheAsideCoordinator()


async def run_cache_aside[T](
    *,
    cache: ICacheStore,
    key: str,
    rule: CacheRule,
    operation: str,
    span: PortCallSpan,
    serialize: Callable[[T], bytes],
    deserialize: Callable[[bytes], T],
    loader: Callable[[], Awaitable[T]],
    coordinator: CacheAsideCoordinator | None = None,
) -> T:
    """Execute cache-aside with fast-path hit, singleflight miss, and size guard."""
    active = coordinator or _coordinator

    cached = await cache.get(key)
    if cached is not None:
        record_cache_hit(operation, key)
        span.cache = "hit"
        return deserialize(cached)

    async with active.singleflight(key):
        cached = await cache.get(key)
        if cached is not None:
            record_cache_hit(operation, key)
            span.cache = "hit"
            return deserialize(cached)

        record_cache_miss(operation, key)
        span.cache = "miss"
        value = await loader()
        payload = serialize(value)
        if payload_within_cache_limit(payload):
            await cache.set(key, payload, rule.ttl_seconds)
        return value
