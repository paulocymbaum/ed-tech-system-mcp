"""Tests for Tavily and YouTube integration clients."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.domain.exceptions import DomainValidationError, ResourceNotFoundError
from mcp_server.domain.schemas import VideoResult
from mcp_server.infrastructure.tavily_search_client import TavilySearchClient
from mcp_server.infrastructure.youtube_client import YouTubeDataApiClient


async def test_tavily_search_maps_api_results() -> None:
    client = TavilySearchClient("api-key")
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {
                "title": "Education overview",
                "content": "A short summary.",
                "url": "https://example.com/education",
            }
        ]
    }

    with patch(
        "mcp_server.infrastructure.tavily_search_client.httpx.AsyncClient"
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        results = await client.search("education", max_results=1)

    assert results == ["Education overview — A short summary. — https://example.com/education"]


async def test_tavily_search_rejects_missing_api_key() -> None:
    client = TavilySearchClient("")
    with pytest.raises(ResourceNotFoundError, match="Tavily API credentials"):
        await client.search("query")


async def test_tavily_search_rejects_empty_query() -> None:
    client = TavilySearchClient("api-key")
    with pytest.raises(DomainValidationError, match="query must not be empty"):
        await client.search("   ")


async def test_youtube_search_maps_sync_results(monkeypatch) -> None:
    client = YouTubeDataApiClient("api-key")

    def fake_search(
        query: str,
        max_results: int,
        language: str,
        safe_search: bool,
    ) -> list[VideoResult]:
        return [
            VideoResult(
                title="Lesson video",
                channel="Teacher",
                url="https://www.youtube.com/watch?v=abc123",
            )
        ]

    monkeypatch.setattr(client, "_search_videos_sync", fake_search)
    videos = await client.search_videos("education", max_results=1)

    assert videos[0].title == "Lesson video"
