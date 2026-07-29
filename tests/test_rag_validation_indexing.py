"""Tests for RAG validation indexing helpers."""

from __future__ import annotations

import pytest

from mcp_server.application.agents.rag_validation.indexing import (
    embed_passages_in_batches,
    resolve_indexed_content_hash,
)
from mcp_server.domain.interfaces import IEmbeddingProvider, IVectorIndexWriter
from mcp_server.domain.schemas import TextChunk


class _BatchRecordingEmbedder(IEmbeddingProvider):
    def __init__(self, *, batch_size_hint: int = 1) -> None:
        self._dimensions = 3
        self.batch_size_hint = batch_size_hint
        self.calls: list[int] = []

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return [[float(index)] * self._dimensions for index, _ in enumerate(texts)]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(len(texts))
        return [[float(index)] * self._dimensions for index, _ in enumerate(texts)]


class _HashWriter(IVectorIndexWriter):
    def __init__(self, *, content_hash: str | None) -> None:
        self._content_hash = content_hash
        self.upsert_calls = 0

    async def get_document_content_hash(self, document_id: str) -> str | None:
        _ = document_id
        return self._content_hash

    async def upsert_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
    ) -> None:
        _ = chunks, embeddings
        self.upsert_calls += 1

    async def delete_by_document_id(self, document_id: str) -> None:
        _ = document_id


@pytest.mark.asyncio
async def test_embed_passages_in_batches_splits_requests() -> None:
    embedder = _BatchRecordingEmbedder()
    vectors = await embed_passages_in_batches(
        embedder,
        ["a", "b", "c", "d", "e"],
        batch_size=2,
    )
    assert embedder.calls == [2, 2, 1]
    assert len(vectors) == 5


@pytest.mark.asyncio
async def test_resolve_indexed_content_hash_uses_writer_lookup() -> None:
    writer = _HashWriter(content_hash="abc123")
    assert await resolve_indexed_content_hash(writer, "doc-1") == "abc123"


@pytest.mark.asyncio
async def test_resolve_indexed_content_hash_returns_none_without_lookup() -> None:
    class _PlainWriter(IVectorIndexWriter):
        async def upsert_chunks(
            self,
            chunks: list[TextChunk],
            embeddings: list[list[float]],
        ) -> None:
            _ = chunks, embeddings

        async def delete_by_document_id(self, document_id: str) -> None:
            _ = document_id

    assert await resolve_indexed_content_hash(_PlainWriter(), "doc-1") is None
