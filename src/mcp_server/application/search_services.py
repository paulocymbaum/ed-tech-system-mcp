"""Web and video search use-cases wrapping integration_runtime ports."""

from __future__ import annotations

from mcp_server.application.integration_runtime import get_search_client, get_video_client
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.interfaces import ISearchClient, IVideoSearchClient
from mcp_server.domain.schemas import VideoResult


async def search_web_snippets(query: str, *, max_results: int = 5) -> list[str]:
    """Search the web via the wired ``ISearchClient``."""
    client = get_search_client()
    if client is None:
        raise ResourceNotFoundError("Web search client has not been initialized")
    if not isinstance(client, ISearchClient):
        raise ResourceNotFoundError("Configured search client is not a web search client")
    return await client.search(query, max_results=max_results)


async def search_videos(
    query: str,
    *,
    max_results: int = 5,
    language: str = "en",
    safe_search: bool = True,
) -> list[VideoResult]:
    """Search YouTube via the wired ``IVideoSearchClient``."""
    client = get_video_client()
    if client is None:
        raise ResourceNotFoundError("Video search client has not been initialized")
    if not isinstance(client, IVideoSearchClient):
        raise ResourceNotFoundError("Configured video client is not a video search client")
    return await client.search_videos(
        query,
        max_results=max_results,
        language=language,
        safe_search=safe_search,
    )
