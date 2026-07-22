"""Infrastructure deferred adapter contract tests (T26–T28)."""

import pytest

from mcp_server.domain.exceptions import DomainValidationError, ResourceNotFoundError
from mcp_server.domain.schemas import VideoResult
from mcp_server.infrastructure.search_client import DuckDuckGoSearchClient
from mcp_server.infrastructure.supabase_client import SupabaseRepository
from mcp_server.infrastructure.youtube_client import YouTubeDataApiClient


async def test_t26_supabase_find_documents_not_implemented() -> None:
    repo = SupabaseRepository("https://test.supabase.co", "key")
    with pytest.raises(NotImplementedError):
        await repo.find_documents("query")


async def test_t26b_supabase_find_documents_rejects_empty_query() -> None:
    repo = SupabaseRepository("https://test.supabase.co", "key")
    with pytest.raises(DomainValidationError, match="query must not be empty"):
        await repo.find_documents("   ")


async def test_t26c_supabase_find_documents_rejects_missing_credentials() -> None:
    repo = SupabaseRepository("", "key")
    with pytest.raises(ResourceNotFoundError, match="Supabase credentials"):
        await repo.find_documents("query")


async def test_t26d_supabase_find_documents_rejects_non_positive_limit() -> None:
    repo = SupabaseRepository("https://test.supabase.co", "key")
    with pytest.raises(DomainValidationError, match="limit must be positive"):
        await repo.find_documents("query", limit=0)


async def test_t26e_supabase_find_documents_rejects_missing_service_role_key() -> None:
    repo = SupabaseRepository("https://test.supabase.co", "")
    with pytest.raises(ResourceNotFoundError, match="Supabase credentials"):
        await repo.find_documents("query")


async def test_t27_youtube_search_videos_maps_api_results(monkeypatch) -> None:
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

    assert len(videos) == 1
    assert videos[0].url.endswith("abc123")


async def test_t27b_youtube_search_videos_rejects_missing_api_key() -> None:
    client = YouTubeDataApiClient("")
    with pytest.raises(ResourceNotFoundError, match="YouTube API credentials"):
        await client.search_videos("query")


async def test_t27c_youtube_search_videos_rejects_non_positive_max_results() -> None:
    client = YouTubeDataApiClient("api-key")
    with pytest.raises(DomainValidationError, match="max_results must be positive"):
        await client.search_videos("query", max_results=0)


async def test_t27d_youtube_search_videos_rejects_empty_query() -> None:
    client = YouTubeDataApiClient("api-key")
    with pytest.raises(DomainValidationError, match="query must not be empty"):
        await client.search_videos("   ")


async def test_t28_duckduckgo_search_not_implemented() -> None:
    client = DuckDuckGoSearchClient()
    with pytest.raises(NotImplementedError):
        await client.search("query")


async def test_t28b_duckduckgo_search_rejects_empty_query() -> None:
    client = DuckDuckGoSearchClient()
    with pytest.raises(DomainValidationError, match="query must not be empty"):
        await client.search("")


async def test_t28c_duckduckgo_search_rejects_non_positive_max_results() -> None:
    client = DuckDuckGoSearchClient()
    with pytest.raises(DomainValidationError, match="max_results must be positive"):
        await client.search("query", max_results=0)
