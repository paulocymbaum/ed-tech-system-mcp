"""Redis and no-op cache store adapters."""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from mcp_server.domain.cache import ICacheStore

logger = logging.getLogger(__name__)


class RedisCacheStore(ICacheStore):
    """Redis-backed cache store with lazy connection and graceful degradation."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: Redis | None = None
        self._available: bool | None = None

    async def _get_client(self) -> Redis | None:
        if self._available is False:
            return None
        if self._client is None:
            try:
                client = Redis.from_url(self._redis_url, decode_responses=False)
                await client.ping()
                self._client = client
                self._available = True
            except RedisError:
                logger.warning(
                    "Redis unavailable; cache reads and writes will be skipped",
                    exc_info=True,
                )
                self._available = False
                self._client = None
                return None
        return self._client

    async def get(self, key: str) -> bytes | None:
        client = await self._get_client()
        if client is None:
            return None
        try:
            value = await client.get(key)
            if value is None:
                return None
            if isinstance(value, bytes):
                return value
            return str(value).encode("utf-8")
        except RedisError:
            logger.warning("Redis GET failed for key %s; treating as cache miss", key)
            self._available = False
            return None

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        client = await self._get_client()
        if client is None:
            return
        try:
            await client.set(key, value, ex=ttl_seconds)
        except RedisError:
            logger.warning("Redis SET failed for key %s; continuing without cache", key)
            self._available = False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class NoOpCacheStore(ICacheStore):
    """Fallback store when caching is disabled or Redis is not configured."""

    async def get(self, key: str) -> bytes | None:
        return None

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        return None
