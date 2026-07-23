"""Tests for deterministic RAG benchmark metrics."""

from __future__ import annotations

from mcp_server.domain.rag_benchmarks import (
    build_retrieval_haystack,
    compute_rag_benchmarks,
    compute_retrieval_proxy_metrics,
    compute_semantic_gold_benchmarks,
    cosine_similarity,
    missing_expected_phrases,
    partition_phrase_matches,
    resolve_score_kind,
    score_thresholds_for_kind,
)
from mcp_server.domain.schemas import ChunkHit


def _chunk(content: str, *, score: float = 0.9, rank: int = 0) -> ChunkHit:
    return ChunkHit(
        id=f"chunk-{rank}",
        document_id="doc-1",
        content=content,
        score=score,
    )


def test_compute_semantic_gold_benchmarks_reports_relevance_and_precision() -> None:
    gold = [1.0, 0.0]
    chunks = [
        [1.0, 0.0],
        [0.7, 0.7141428],
        [0.0, 1.0],
    ]
    max_rel, mean_rel, precision, rank_reciprocal = compute_semantic_gold_benchmarks(
        gold_embedding=gold,
        chunk_embeddings=chunks,
        relevance_threshold=0.75,
    )
    assert max_rel == 1.0
    assert round(mean_rel, 2) == 0.57
    assert precision == 1 / 3
    assert rank_reciprocal == 1.0


def test_cosine_similarity_returns_zero_for_empty_vectors() -> None:
    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [0.0, 0.0]) == 0.0


def test_compute_rag_benchmarks_perfect_coverage() -> None:
    chunks = [
        _chunk("Photosynthesis uses chlorophyll.", rank=0),
        _chunk("Glucose is produced in light reactions.", rank=1),
    ]
    scores = compute_rag_benchmarks(
        expected_phrases=["chlorophyll", "glucose"],
        chunks=chunks,
        merged_context="",
    )
    assert scores.phrase_coverage == 1.0
    assert scores.any_phrase_hit == 1.0
    assert scores.first_phrase_rank_reciprocal == 1.0
    assert scores.matched_phrase_count == 2


def test_compute_rag_benchmarks_partial_coverage_and_rank() -> None:
    chunks = [
        _chunk("Unrelated intro.", rank=0),
        _chunk("Chlorophyll absorbs light.", rank=1),
    ]
    scores = compute_rag_benchmarks(
        expected_phrases=["chlorophyll", "glucose"],
        chunks=chunks,
        merged_context="",
    )
    assert scores.phrase_coverage == 0.5
    assert scores.any_phrase_hit == 1.0
    assert scores.first_phrase_rank_reciprocal == 0.5
    assert scores.phrase_chunk_rate == 0.5


def test_compute_rag_benchmarks_empty_expected_phrases() -> None:
    scores = compute_rag_benchmarks(
        expected_phrases=[],
        chunks=[_chunk("any")],
        merged_context="",
    )
    assert scores.phrase_coverage == 1.0
    assert scores.expected_phrase_count == 0


def test_compute_retrieval_proxy_metrics() -> None:
    chunks = [_chunk("a", score=0.8, rank=0), _chunk("b", score=0.6, rank=1)]
    metrics = compute_retrieval_proxy_metrics(
        chunks=chunks,
        merged_context="merged",
        score_kind="cosine",
    )
    assert metrics.chunk_count == 2
    assert metrics.mean_chunk_score == 0.7
    assert metrics.max_chunk_score == 0.8
    assert metrics.context_length_chars == len("merged")
    assert metrics.score_kind == "cosine"
    assert metrics.effective_k == 2


def test_missing_expected_phrases_uses_chunks_only() -> None:
    chunks = [_chunk("Unrelated body.", rank=0)]
    missing = missing_expected_phrases(
        ["chlorophyll", "glucose"],
        chunks=chunks,
        merged_context="Photosynthesis uses chlorophyll.",
    )
    assert missing == ["chlorophyll", "glucose"]


def test_build_retrieval_haystack_ignores_merged_context() -> None:
    chunks = [_chunk("chunk body only", rank=0)]
    haystack = build_retrieval_haystack(chunks, merged_context="duplicate duplicate duplicate")
    assert "chunk body only" in haystack
    assert "duplicate" not in haystack


def test_partition_phrase_matches_returns_structured_lists() -> None:
    chunks = [_chunk("Chlorophyll absorbs light.", rank=0)]
    matched, missing = partition_phrase_matches(
        ["chlorophyll", "glucose"],
        chunks=chunks,
    )
    assert matched == ["chlorophyll"]
    assert missing == ["glucose"]


def test_resolve_score_kind_routing() -> None:
    assert (
        resolve_score_kind(
            rerank_applied=True,
            retrieval_mode="vector",
            hybrid_fts_active=False,
        )
        == "reranker"
    )
    assert (
        resolve_score_kind(
            rerank_applied=False,
            retrieval_mode="hybrid",
            hybrid_fts_active=True,
        )
        == "rrf"
    )
    assert (
        resolve_score_kind(
            rerank_applied=False,
            retrieval_mode="hybrid",
            hybrid_fts_active=False,
        )
        == "cosine"
    )
    assert (
        resolve_score_kind(
            rerank_applied=False,
            retrieval_mode="vector",
            hybrid_fts_active=False,
        )
        == "cosine"
    )


def test_score_thresholds_for_kind_rrf_differs_from_cosine() -> None:
    cosine = score_thresholds_for_kind("cosine")
    rrf = score_thresholds_for_kind("rrf")
    assert cosine.good > rrf.good
    assert rrf.good == 0.02
    assert rrf.warn == 0.01


def test_score_thresholds_for_kind_reranker_uses_sigmoid_cutoffs() -> None:
    reranker = score_thresholds_for_kind("reranker")
    cosine = score_thresholds_for_kind("cosine")
    assert reranker.good == 0.5
    assert reranker.warn == 0.02
    assert reranker.good < cosine.good


def test_compute_retrieval_proxy_metrics_empty_chunks() -> None:
    metrics = compute_retrieval_proxy_metrics(
        chunks=[],
        merged_context="empty context",
        score_kind="rrf",
    )
    assert metrics.chunk_count == 0
    assert metrics.mean_chunk_score == 0.0
    assert metrics.max_chunk_score == 0.0
    assert metrics.context_length_chars == len("empty context")
    assert metrics.score_kind == "rrf"
    assert metrics.effective_k == 0


def test_rag_benchmark_scores_as_dict_keys() -> None:
    scores = compute_rag_benchmarks(
        expected_phrases=["chlorophyll"],
        chunks=[_chunk("Chlorophyll absorbs light.", rank=0)],
        merged_context="",
    )
    payload = scores.as_dict()
    assert set(payload) == {
        "phrase_coverage",
        "phrase_chunk_rate",
        "any_phrase_hit",
        "first_phrase_rank_reciprocal",
        "expected_phrase_count",
        "matched_phrase_count",
        "retrieved_chunk_count",
        "gold_semantic_relevance",
        "mean_gold_semantic_relevance",
        "gold_semantic_precision",
        "gold_semantic_rank_reciprocal",
    }
