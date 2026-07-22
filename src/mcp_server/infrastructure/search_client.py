"""Open-source web search implementation."""

from mcp_server.domain.interfaces import ISearchClient
from mcp_server.domain.invariants import require_non_empty_text, require_positive_int


class DuckDuckGoSearchClient(ISearchClient):
    """Adapter for DuckDuckGo web search."""

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        query = require_non_empty_text(query, field="query")
        max_results = require_positive_int(max_results, field="max_results")
        raise NotImplementedError("DuckDuckGoSearchClient.search is not yet implemented")
