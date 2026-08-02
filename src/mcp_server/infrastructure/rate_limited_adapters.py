"""Rate-limited decorators for outbound domain ports."""

from __future__ import annotations

from mcp_server.domain.external_rate_limit import IExternalRequestRateLimiter
from mcp_server.domain.interfaces import IDataRepository, ISearchClient, IVideoSearchClient
from mcp_server.domain.schemas import ChunkHit, ChunkRetrievalFilter, DocumentHit, VideoResult


class RateLimitedDataRepository(IDataRepository):
    """Reserve external quota before Supabase document lookups."""

    def __init__(
        self,
        inner: IDataRepository,
        limiter: IExternalRequestRateLimiter,
        *,
        provider: str = "supabase",
    ) -> None:
        self._inner = inner
        self._limiter = limiter
        self._provider = provider

    async def find_documents(
        self,
        query: str,
        limit: int = 10,
        *,
        filters: ChunkRetrievalFilter | None = None,
    ) -> list[DocumentHit]:
        await self._limiter.acquire(provider=self._provider)
        return await self._inner.find_documents(query, limit=limit, filters=filters)


class RateLimitedSearchClient(ISearchClient):
    """Reserve external quota before web search calls."""

    def __init__(
        self,
        inner: ISearchClient,
        limiter: IExternalRequestRateLimiter,
        *,
        provider: str = "web_search",
    ) -> None:
        self._inner = inner
        self._limiter = limiter
        self._provider = provider

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        await self._limiter.acquire(provider=self._provider)
        return await self._inner.search(query, max_results=max_results)


class RateLimitedVideoSearchClient(IVideoSearchClient):
    """Reserve external quota before YouTube API calls."""

    def __init__(
        self,
        inner: IVideoSearchClient,
        limiter: IExternalRequestRateLimiter,
        *,
        provider: str = "youtube",
    ) -> None:
        self._inner = inner
        self._limiter = limiter
        self._provider = provider

    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        await self._limiter.acquire(provider=self._provider)
        return await self._inner.search_videos(
            query,
            max_results=max_results,
            language=language,
            safe_search=safe_search,
        )
