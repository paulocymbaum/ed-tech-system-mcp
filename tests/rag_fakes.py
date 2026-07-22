"""Shared RAG test doubles for graph and API tests."""

from __future__ import annotations

from typing import Literal

from mcp_server.domain.interfaces import (
    IChunkingStrategy,
    IEmbeddingProvider,
    IVectorRetriever,
)
from mcp_server.domain.schemas import ChunkHit, ChunkRetrievalFilter, TextChunk
from mcp_server.infrastructure.chunking.langchain_chunking_adapter import LangChainChunkingAdapter


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
    def __init__(self, *, supports_hybrid_fts: bool = False) -> None:
        self.last_mode: str | None = None
        self.last_query_text: str | None = None
        self._supports_hybrid_fts = supports_hybrid_fts

    @property
    def supports_hybrid_fts(self) -> bool:
        return self._supports_hybrid_fts

    async def retrieve(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        filters: ChunkRetrievalFilter,
        mode: Literal["vector", "hybrid"],
        query_text: str | None = None,
    ) -> list[ChunkHit]:
        _ = query_embedding, filters
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
        self._adapter = LangChainChunkingAdapter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    @property
    def chunk_size(self) -> int:
        return self._adapter.chunk_size

    @property
    def chunk_overlap(self) -> int:
        return self._adapter.chunk_overlap

    def chunk(
        self,
        text: str,
        *,
        document_id: str,
        language: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[TextChunk]:
        return self._adapter.chunk(
            text,
            document_id=document_id,
            language=language,
            metadata=metadata,
        )


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


def _query_tokens(query_text: str | None) -> set[str]:
    if not query_text:
        return set()
    return {token.lower() for token in query_text.split() if token.strip()}


class FixtureAwareRetriever(FakeVectorRetriever):
    """Return indexed chunks ranked by vector order; hybrid boosts keyword overlap."""

    def __init__(self, writer: RecordingIndexWriter) -> None:
        super().__init__(supports_hybrid_fts=True)
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
        _ = query_embedding, filters
        self.last_mode = mode
        self.last_query_text = query_text
        if not self._writer.chunks:
            return []

        query_tokens = _query_tokens(query_text)
        ranked: list[tuple[float, int, TextChunk]] = []
        for index, chunk in enumerate(self._writer.chunks):
            base_score = max(0.55, 0.95 - (index * 0.08))
            keyword_boost = 0.0
            if mode == "hybrid" and query_tokens:
                content_lower = chunk.content.lower()
                overlap = sum(1 for token in query_tokens if token in content_lower)
                keyword_boost = min(0.25, overlap * 0.05)
            ranked.append((base_score + keyword_boost, index, chunk))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        hits: list[ChunkHit] = []
        for score, index, chunk in ranked[:limit]:
            hits.append(
                ChunkHit(
                    id=f"chunk-fixture-{index}",
                    document_id=chunk.document_id,
                    title=f"Fixture chunk {index + 1}",
                    content=chunk.content,
                    score=round(min(score, 0.99), 4),
                )
            )
        return hits
