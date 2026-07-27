"""Tests for semantic gold-answer benchmark enrichment."""

from __future__ import annotations

import pytest

from mcp_server.application.agents.rag_validation.semantic_benchmarks import (
    enrich_benchmarks_with_gold_semantic,
)
from mcp_server.domain.rag_benchmarks import RagBenchmarkScores
from mcp_server.domain.schemas import ChunkHit
from rag_fakes import FakeEmbeddingProvider


def _empty_benchmarks() -> RagBenchmarkScores:
    return RagBenchmarkScores(
        phrase_coverage=0.0,
        phrase_chunk_rate=0.0,
        any_phrase_hit=0.0,
        first_phrase_rank_reciprocal=0.0,
        expected_phrase_count=0,
        matched_phrase_count=0,
        retrieved_chunk_count=0,
    )


@pytest.mark.asyncio
async def test_enrich_benchmarks_with_gold_semantic_uses_embedder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp_server.application import retrieval_runtime

    embedder = FakeEmbeddingProvider()
    monkeypatch.setattr(retrieval_runtime, "_embedding_provider", embedder)

    chunks = [
        ChunkHit(
            id="c1",
            document_id="doc",
            content="API keys are passed as a bearer token in the Authorization header.",
            score=0.9,
        ),
        ChunkHit(
            id="c2",
            document_id="doc",
            content="Unrelated boilerplate about authentication patterns in production systems.",
            score=0.4,
        ),
    ]
    enriched = await enrich_benchmarks_with_gold_semantic(
        _empty_benchmarks(),
        gold_answer="API keys are passed as a bearer token in the Authorization header.",
        chunks=chunks,
        relevance_threshold=0.55,
    )

    assert enriched.gold_semantic_relevance > enriched.mean_gold_semantic_relevance
    assert enriched.gold_semantic_precision > 0.0
    assert enriched.gold_semantic_precision < 1.0
