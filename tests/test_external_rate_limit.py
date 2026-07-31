"""Tests for external API rate limiting."""

from __future__ import annotations

import pytest

from mcp_server.domain.exceptions import ExternalRateLimitError
from mcp_server.domain.external_rate_limit import EXTERNAL_RATE_LIMIT_MESSAGE
from mcp_server.infrastructure.external_rate_limiter import SlidingWindowExternalRequestRateLimiter
from mcp_server.infrastructure.rate_limited_adapters import RateLimitedSearchClient
from mcp_server.infrastructure.tavily_search_client import TavilySearchClient


class _CountingSearchClient:
    def __init__(self) -> None:
        self.calls = 0

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        del query, max_results
        self.calls += 1
        return ["ok"]


async def test_rate_limiter_allows_calls_under_limit() -> None:
    limiter = SlidingWindowExternalRequestRateLimiter(3)
    inner = _CountingSearchClient()
    client = RateLimitedSearchClient(inner, limiter)

    for _ in range(3):
        assert await client.search("plants") == ["ok"]

    assert inner.calls == 3


async def test_rate_limiter_raises_wait_message_when_exceeded() -> None:
    limiter = SlidingWindowExternalRequestRateLimiter(2)
    inner = _CountingSearchClient()
    client = RateLimitedSearchClient(inner, limiter)

    await client.search("plants")
    await client.search("plants")

    with pytest.raises(ExternalRateLimitError, match="wait a few minutes"):
        await client.search("plants")

    assert str(ExternalRateLimitError(EXTERNAL_RATE_LIMIT_MESSAGE)) == EXTERNAL_RATE_LIMIT_MESSAGE
    assert inner.calls == 2


async def test_rate_limited_tavily_still_validates_before_quota() -> None:
    limiter = SlidingWindowExternalRequestRateLimiter(5)
    client = RateLimitedSearchClient(TavilySearchClient("api-key"), limiter)

    from mcp_server.domain.exceptions import DomainValidationError

    with pytest.raises(DomainValidationError, match="query must not be empty"):
        await client.search("   ")
