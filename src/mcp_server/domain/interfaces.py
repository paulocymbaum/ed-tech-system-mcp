"""Abstract base classes (ports) for external integrations."""

from abc import ABC, abstractmethod
from typing import Literal

from mcp_server.domain.schemas import (
    ChunkHit,
    ChunkRetrievalFilter,
    DocumentHit,
    TextChunk,
    VideoResult,
)


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


class IChunkingStrategy(ABC):
    """Port for splitting document text into indexable chunks."""

    @abstractmethod
    def chunk(
        self,
        text: str,
        *,
        document_id: str,
        language: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[TextChunk]:
        """Split text into ordered chunks with stable content hashes."""


class IEmbeddingProvider(ABC):
    """Port for local embedding inference (E5 query/passage prefixes in adapter)."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding vector dimension for the configured model."""

    @abstractmethod
    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed search queries (E5 ``query:`` prefix applied by adapter)."""

    @abstractmethod
    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Embed document passages (E5 ``passage:`` prefix applied by adapter)."""


class IVectorRetriever(ABC):
    """Port for semantic chunk retrieval from a vector index."""

    @abstractmethod
    async def retrieve(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        filters: ChunkRetrievalFilter,
        mode: Literal["vector", "hybrid"],
        query_text: str | None = None,
    ) -> list[ChunkHit]:
        """Return ranked chunk hits for the query embedding."""


class IVectorIndexWriter(ABC):
    """Port for index-time chunk upsert and document-scoped deletion."""

    @abstractmethod
    async def upsert_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        """Persist chunks and embeddings, replacing stale rows for each document."""

    @abstractmethod
    async def delete_by_document_id(self, document_id: str) -> None:
        """Remove all chunks for a document (soft or hard delete per adapter)."""


class IReranker(ABC):
    """Port for cross-encoder re-ranking of retrieval candidates."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[ChunkHit],
        *,
        top_n: int,
    ) -> list[ChunkHit]:
        """Return candidates re-ordered and truncated to top_n."""
