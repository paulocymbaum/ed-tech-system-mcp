"""Open-source web search implementation."""

from mcp_server.domain.interfaces import ISearchClient


class DuckDuckGoSearchClient(ISearchClient):
    """Adapter for DuckDuckGo web search."""

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        raise NotImplementedError("DuckDuckGoSearchClient.search is not yet implemented")
