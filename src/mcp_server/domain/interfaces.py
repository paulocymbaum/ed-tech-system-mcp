"""Abstract base classes (ports) for external integrations."""

from abc import ABC, abstractmethod

from mcp_server.domain.schemas import DocumentHit, VideoResult


class IDataRepository(ABC):
    """Port for structured document storage and retrieval."""

    @abstractmethod
    async def find_documents(self, query: str, limit: int = 10) -> list[DocumentHit]:
        """Return documents matching the given query."""


class ISearchClient(ABC):
    """Port for open-source web search."""

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[str]:
        """Return search result snippets for the query."""


class IVideoSearchClient(ABC):
    """Port for educational video discovery."""

    @abstractmethod
    async def search_videos(
        self,
        query: str,
        max_results: int = 5,
        language: str = "en",
        safe_search: bool = True,
    ) -> list[VideoResult]:
        """Return normalized video results for the query."""
