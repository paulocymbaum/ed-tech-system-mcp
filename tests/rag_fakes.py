"""Shared RAG test doubles for graph and API tests."""

from __future__ import annotations

from typing import Literal

from mcp_server.domain.interfaces import IChunkingStrategy, IEmbeddingProvider, IReranker, IVectorRetriever
from mcp_server.domain.schemas import ChunkHit, ChunkRetrievalFilter, TextChunk


class FakeEmbeddingProvider(IEmbeddingProvider):
    def __init__(self, dimensions: int = 384) -> None:
        self._dimensions = dimensions
        self.queries: list[str] = []
        self.passages: list[str] = []

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        self.queries.extend(texts)
        return [
            [float(index) / self._dimensions for index in range(self._dimensions)] for _ in texts
        ]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        self.passages.extend(texts)
        return [[1.0] + [0.0] * (self._dimensions - 1) for _ in texts]


class FakeVectorRetriever(IVectorRetriever):
    def __init__(self) -> None:
        self.last_mode: str | None = None
        self.last_query_text: str | None = None

    async def retrieve(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        filters: ChunkRetrievalFilter,
        mode: Literal["vector", "hybrid"],
        query_text: str | None = None,
    ) -> list[ChunkHit]:
        _ = query_embedding, limit, filters
        self.last_mode = mode
        self.last_query_text = query_text
        return [
            ChunkHit(
                id="chunk-1",
                document_id="doc-1",
                title="Intro",
                content="Photosynthesis converts light to energy.",
                score=0.92,
            )
        ]


class FakeChunkingStrategy(IChunkingStrategy):
    def __init__(self, *, chunk_size: int = 400, chunk_overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    @property
    def chunk_size(self) -> int:
        return self._chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._chunk_overlap

    def chunk(
        self,
        text: str,
        *,
        document_id: str,
        language: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[TextChunk]:
        _ = language, metadata
        return [
            TextChunk(
                document_id=document_id,
                chunk_index=0,
                content=text,
                content_hash="fixture-hash",
            )
        ]


class RecordingIndexWriter:
    def __init__(self) -> None:
        self.chunks: list[TextChunk] = []

    async def upsert_document(self, **kwargs: object) -> None:
        _ = kwargs

    async def upsert_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        _ = embeddings
        self.chunks = chunks

    async def delete_by_document_id(self, document_id: str) -> None:
        _ = document_id


class FixtureAwareRetriever(FakeVectorRetriever):
    def __init__(self, writer: RecordingIndexWriter) -> None:
        super().__init__()
        self._writer = writer

    async def retrieve(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        filters: ChunkRetrievalFilter,
        mode: Literal["vector", "hybrid"],
        query_text: str | None = None,
    ) -> list[ChunkHit]:
        _ = query_embedding, limit, filters, mode, query_text
        if not self._writer.chunks:
            return []
        chunk = self._writer.chunks[0]
        return [
            ChunkHit(
                id="chunk-fixture-1",
                document_id=chunk.document_id,
                title="Photosynthesis fixture",
                content=chunk.content,
                score=0.95,
            )
        ]
