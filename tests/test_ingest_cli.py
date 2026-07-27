"""Tests for document ingest CLI parent upsert ordering."""

from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from mcp_server.domain.interfaces import IChunkingStrategy, IEmbeddingProvider
from mcp_server.domain.schemas import TextChunk
from mcp_server.infrastructure.retrieval.supabase_vector_index_writer import (
    SupabaseVectorIndexWriter,
)

_INGEST_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ingest" / "index_documents.py"


def _load_ingest_module():
    spec = importlib.util.spec_from_file_location("index_documents", _INGEST_PATH)
    if spec is None or spec.loader is None:
        msg = f"Unable to load ingest module from {_INGEST_PATH}"
        raise RuntimeError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules["index_documents"] = module
    spec.loader.exec_module(module)
    return module


class _FakeChunkingStrategy(IChunkingStrategy):
    def chunk(
        self,
        text: str,
        *,
        document_id: str,
        language: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> list[TextChunk]:
        _ = text, language, metadata
        return [
            TextChunk(
                document_id=document_id,
                content="chunk one",
                content_hash="hash-1",
                chunk_index=0,
            )
        ]


class _FakeEmbeddingProvider(IEmbeddingProvider):
    @property
    def dimensions(self) -> int:
        return 384

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]


@pytest.mark.asyncio
async def test_ingest_upserts_parent_document_before_chunks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ingest = _load_ingest_module()
    document_id = "11111111-1111-1111-1111-111111111111"
    text_file = tmp_path / "lesson.txt"
    text_file.write_text("Lesson content for ingest test.", encoding="utf-8")

    call_order: list[str] = []
    writer = SupabaseVectorIndexWriter("https://test.supabase.co", "service-key")

    async def track_upsert_document(**kwargs: object) -> None:
        _ = kwargs
        call_order.append("upsert_document")

    async def track_upsert_chunks(chunks: list[TextChunk], embeddings: list[list[float]]) -> None:
        _ = chunks, embeddings
        call_order.append("upsert_chunks")

    writer.upsert_document = track_upsert_document  # type: ignore[method-assign]
    writer.upsert_chunks = track_upsert_chunks  # type: ignore[method-assign]

    monkeypatch.setattr(ingest, "load_settings", lambda: object())
    monkeypatch.setattr(ingest, "create_cache_store", lambda settings: None)
    monkeypatch.setattr(ingest, "build_chunking_strategy", lambda settings: _FakeChunkingStrategy())
    monkeypatch.setattr(
        ingest,
        "build_embedding_provider",
        lambda settings, cache_store: _FakeEmbeddingProvider(),
    )
    monkeypatch.setattr(ingest, "build_vector_index_writer", lambda settings: writer)

    args = Namespace(
        document_id=document_id,
        title="Lesson title",
        file=text_file,
        language="en",
        course_id="course-1",
    )
    await ingest._ingest(args)

    assert call_order == ["upsert_document", "upsert_chunks"]
