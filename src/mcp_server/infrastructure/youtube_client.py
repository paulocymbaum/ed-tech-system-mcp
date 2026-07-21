"""YouTube Data API adapter for educational video search."""

from mcp_server.domain.interfaces import IVideoSearchClient
from mcp_server.domain.schemas import VideoResult


class YouTubeDataApiClient(IVideoSearchClient):
    """Adapter for YouTube Data API v3."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        raise NotImplementedError("YouTubeDataApiClient.search_videos is not yet implemented")
