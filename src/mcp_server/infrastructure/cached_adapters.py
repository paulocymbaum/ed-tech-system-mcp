"""Cache-aside decorators for domain ports."""

from __future__ import annotations

from mcp_server.domain.cache import (
    CacheOperationType,
    CacheRuleSet,
    ICacheStore,
    build_cache_key,
)
from mcp_server.domain.interfaces import ISearchClient, IVideoSearchClient
from mcp_server.domain.schemas import VideoResult
from mcp_server.infrastructure.cache_aside import run_cache_aside
from mcp_server.infrastructure.cache_serialization import (
    deserialize_snippets,
    deserialize_videos,
    serialize_snippets,
    serialize_videos,
)
from mcp_server.infrastructure.port_observability import port_call_span


class CachedSearchClient(ISearchClient):
    """Cache-aside wrapper for web search."""

    def __init__(
        self,
        inner: ISearchClient,
        cache: ICacheStore,
        rules: CacheRuleSet,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._rules = rules

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        operation = CacheOperationType.WEB_SEARCH
        async with port_call_span(operation.value) as span:
            rule = self._rules.for_operation(operation)
            if rule is None or not rule.enabled:
                span.cache = "disabled"
                return await self._inner.search(query, max_results=max_results)

            key = build_cache_key(
                operation,
                {"query": query, "max_results": max_results},
                prefix=rule.key_prefix,
            )
            return await run_cache_aside(
                cache=self._cache,
                key=key,
                rule=rule,
                operation=operation.value,
                span=span,
                serialize=serialize_snippets,
                deserialize=deserialize_snippets,
                loader=lambda: self._inner.search(query, max_results=max_results),
            )


class CachedVideoSearchClient(IVideoSearchClient):
    """Cache-aside wrapper for video search."""

    def __init__(
        self,
        inner: IVideoSearchClient,
        cache: ICacheStore,
        rules: CacheRuleSet,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._rules = rules

    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        operation = CacheOperationType.YOUTUBE_SEARCH_VIDEOS
        async with port_call_span(operation.value) as span:
            rule = self._rules.for_operation(operation)
            if rule is None or not rule.enabled:
                span.cache = "disabled"
                return await self._inner.search_videos(
                    query,
                    max_results=max_results,
                    language=language,
                    safe_search=safe_search,
                )

            key = build_cache_key(
                operation,
                {
                    "query": query,
                    "max_results": max_results,
                    "language": language,
                    "safe_search": safe_search,
                },
                prefix=rule.key_prefix,
            )
            return await run_cache_aside(
                cache=self._cache,
                key=key,
                rule=rule,
                operation=operation.value,
                span=span,
                serialize=serialize_videos,
                deserialize=deserialize_videos,
                loader=lambda: self._inner.search_videos(
                    query,
                    max_results=max_results,
                    language=language,
                    safe_search=safe_search,
                ),
            )
