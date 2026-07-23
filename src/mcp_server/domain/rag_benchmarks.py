"""Deterministic open-source RAG quality metrics for local validation and UI tests."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

from mcp_server.domain.schemas import ChunkHit

ScoreKind = Literal["cosine", "rrf", "reranker"]
RetrievalMode = Literal["vector", "hybrid"]

# Minimum cosine similarity (query embedding vs passage embedding) to count a chunk as
# semantically relevant to the gold answer when computing precision@k.
DEFAULT_GOLD_SEMANTIC_PRECISION_THRESHOLD = 0.55


@dataclass(frozen=True, slots=True)
class ScoreThresholds:
    """Good/warn cutoffs for chunk scores, calibrated per score kind."""

    good: float
    warn: float


@dataclass(frozen=True, slots=True)
class RagEvaluationContext:
    """Run configuration affecting how retrieval metrics should be interpreted."""

    retrieval_mode: RetrievalMode
    retrieve_limit: int
    rerank_enabled: bool
    rerank_top_n: int
    effective_k: int
    score_kind: ScoreKind
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    indexed_chunk_count: int | None = None
    hybrid_fts_active: bool = False
    rerank_applied: bool = False

    def as_dict(self) -> dict[str, str | int | bool | None]:
        return {
            "retrieval_mode": self.retrieval_mode,
            "retrieve_limit": self.retrieve_limit,
            "rerank_enabled": self.rerank_enabled,
            "rerank_top_n": self.rerank_top_n,
            "effective_k": self.effective_k,
            "score_kind": self.score_kind,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "indexed_chunk_count": self.indexed_chunk_count,
            "hybrid_fts_active": self.hybrid_fts_active,
            "rerank_applied": self.rerank_applied,
        }


@dataclass(frozen=True, slots=True)
class RagBenchmarkScores:
    """Phrase-grounded retrieval quality metrics (no LLM judge required)."""

    phrase_coverage: float
    phrase_chunk_rate: float
    any_phrase_hit: float
    first_phrase_rank_reciprocal: float
    expected_phrase_count: int
    matched_phrase_count: int
    retrieved_chunk_count: int
    gold_semantic_relevance: float = 0.0
    mean_gold_semantic_relevance: float = 0.0
    gold_semantic_precision: float = 0.0
    gold_semantic_rank_reciprocal: float = 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "phrase_coverage": self.phrase_coverage,
            "phrase_chunk_rate": self.phrase_chunk_rate,
            "any_phrase_hit": self.any_phrase_hit,
            "first_phrase_rank_reciprocal": self.first_phrase_rank_reciprocal,
            "expected_phrase_count": self.expected_phrase_count,
            "matched_phrase_count": self.matched_phrase_count,
            "retrieved_chunk_count": self.retrieved_chunk_count,
            "gold_semantic_relevance": self.gold_semantic_relevance,
            "mean_gold_semantic_relevance": self.mean_gold_semantic_relevance,
            "gold_semantic_precision": self.gold_semantic_precision,
            "gold_semantic_rank_reciprocal": self.gold_semantic_rank_reciprocal,
        }

    def with_semantic_gold_scores(
        self,
        *,
        gold_semantic_relevance: float,
        mean_gold_semantic_relevance: float,
        gold_semantic_precision: float,
        gold_semantic_rank_reciprocal: float,
    ) -> RagBenchmarkScores:
        """Return a copy with semantic gold-answer metrics attached."""
        return replace(
            self,
            gold_semantic_relevance=round(gold_semantic_relevance, 4),
            mean_gold_semantic_relevance=round(mean_gold_semantic_relevance, 4),
            gold_semantic_precision=round(gold_semantic_precision, 4),
            gold_semantic_rank_reciprocal=round(gold_semantic_rank_reciprocal, 4),
        )


@dataclass(frozen=True, slots=True)
class RetrievalProxyMetrics:
    """Retrieval-only proxies when no ground-truth phrases are available."""

    chunk_count: int
    mean_chunk_score: float
    max_chunk_score: float
    context_length_chars: int
    score_kind: ScoreKind
    effective_k: int

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "chunk_count": self.chunk_count,
            "mean_chunk_score": self.mean_chunk_score,
            "max_chunk_score": self.max_chunk_score,
            "context_length_chars": self.context_length_chars,
            "score_kind": self.score_kind,
            "effective_k": self.effective_k,
        }


def score_thresholds_for_kind(score_kind: ScoreKind) -> ScoreThresholds:
    """Return good/warn thresholds calibrated for the given chunk score semantics."""
    if score_kind == "rrf":
        return ScoreThresholds(good=0.02, warn=0.01)
    if score_kind == "reranker":
        # Cross-encoder logits are mapped through sigmoid before display.
        return ScoreThresholds(good=0.5, warn=0.02)
    return ScoreThresholds(good=0.75, warn=0.45)


def resolve_score_kind(
    *,
    rerank_applied: bool,
    retrieval_mode: RetrievalMode,
    hybrid_fts_active: bool,
) -> ScoreKind:
    """Infer chunk score semantics from the retrieval path taken."""
    if rerank_applied:
        return "reranker"
    if retrieval_mode == "hybrid" and hybrid_fts_active:
        return "rrf"
    return "cosine"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Cosine similarity between two L2-normalized or arbitrary vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def compute_semantic_gold_benchmarks(
    *,
    gold_embedding: list[float],
    chunk_embeddings: list[list[float]],
    relevance_threshold: float = DEFAULT_GOLD_SEMANTIC_PRECISION_THRESHOLD,
) -> tuple[float, float, float, float]:
    """Compute semantic relevance and precision vs a gold-answer embedding.

    Returns:
        (max_relevance, mean_relevance, precision_at_k, rank_reciprocal)
    """
    if not gold_embedding or not chunk_embeddings:
        return 0.0, 0.0, 0.0, 0.0

    similarities = [cosine_similarity(gold_embedding, vector) for vector in chunk_embeddings]
    max_relevance = max(similarities)
    mean_relevance = sum(similarities) / len(similarities)
    relevant_count = sum(1 for value in similarities if value >= relevance_threshold)
    precision = relevant_count / len(similarities)

    best_rank: int | None = None
    for index, value in enumerate(similarities, start=1):
        if value >= relevance_threshold:
            best_rank = index
            break
    rank_reciprocal = 1.0 / best_rank if best_rank is not None else 0.0

    return max_relevance, mean_relevance, precision, rank_reciprocal


def _normalize_phrases(phrases: list[str]) -> list[str]:
    return [phrase.strip().lower() for phrase in phrases if phrase.strip()]


def _chunk_contains_phrase(chunk: ChunkHit, phrase: str) -> bool:
    return phrase in chunk.content.lower()


def build_retrieval_haystack(chunks: list[ChunkHit], *, merged_context: str = "") -> str:
    """Lowercase chunk bodies for phrase matching (chunks are the source of truth)."""
    del merged_context  # retained for call-site compatibility; not used in matching
    return "\n".join(chunk.content.lower() for chunk in chunks)


def partition_phrase_matches(
    expected_phrases: list[str],
    *,
    chunks: list[ChunkHit],
    merged_context: str = "",
) -> tuple[list[str], list[str]]:
    """Return (matched, missing) original phrases based on chunk content only."""
    haystack = build_retrieval_haystack(chunks, merged_context=merged_context)
    matched: list[str] = []
    missing: list[str] = []
    for phrase in expected_phrases:
        if not phrase.strip():
            continue
        if phrase.lower() in haystack:
            matched.append(phrase)
        else:
            missing.append(phrase)
    return matched, missing


def missing_expected_phrases(
    expected_phrases: list[str],
    *,
    chunks: list[ChunkHit],
    merged_context: str = "",
) -> list[str]:
    """Return original phrases not found in retrieved chunks."""
    _, missing = partition_phrase_matches(
        expected_phrases,
        chunks=chunks,
        merged_context=merged_context,
    )
    return missing


def compute_rag_benchmarks(
    *,
    expected_phrases: list[str],
    chunks: list[ChunkHit],
    merged_context: str = "",
) -> RagBenchmarkScores:
    """Compute deterministic RAG benchmarks from expected phrases and retrieved chunks."""
    phrases = _normalize_phrases(expected_phrases)
    haystack = build_retrieval_haystack(chunks, merged_context=merged_context)

    if not phrases:
        return RagBenchmarkScores(
            phrase_coverage=1.0,
            phrase_chunk_rate=1.0 if chunks else 0.0,
            any_phrase_hit=1.0 if chunks else 0.0,
            first_phrase_rank_reciprocal=0.0,
            expected_phrase_count=0,
            matched_phrase_count=0,
            retrieved_chunk_count=len(chunks),
        )

    matched = [phrase for phrase in phrases if phrase in haystack]
    phrase_coverage = len(matched) / len(phrases)

    relevant_chunks = 0
    first_relevant_rank: int | None = None
    for index, chunk in enumerate(chunks, start=1):
        if any(_chunk_contains_phrase(chunk, phrase) for phrase in phrases):
            relevant_chunks += 1
            if first_relevant_rank is None:
                first_relevant_rank = index

    phrase_chunk_rate = relevant_chunks / len(chunks) if chunks else 0.0
    any_phrase_hit = 1.0 if first_relevant_rank is not None else 0.0
    first_phrase_rank_reciprocal = (
        1.0 / first_relevant_rank if first_relevant_rank is not None else 0.0
    )

    return RagBenchmarkScores(
        phrase_coverage=round(phrase_coverage, 4),
        phrase_chunk_rate=round(phrase_chunk_rate, 4),
        any_phrase_hit=round(any_phrase_hit, 4),
        first_phrase_rank_reciprocal=round(first_phrase_rank_reciprocal, 4),
        expected_phrase_count=len(phrases),
        matched_phrase_count=len(matched),
        retrieved_chunk_count=len(chunks),
    )


def build_rag_evaluation_context(
    *,
    retrieval_mode: RetrievalMode,
    retrieve_limit: int,
    rerank_enabled: bool,
    rerank_top_n: int,
    chunks: list[ChunkHit],
    rerank_applied: bool,
    hybrid_fts_active: bool,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    indexed_chunk_count: int | None = None,
) -> RagEvaluationContext:
    """Build evaluation context describing the retrieval run configuration."""
    return RagEvaluationContext(
        retrieval_mode=retrieval_mode,
        retrieve_limit=retrieve_limit,
        rerank_enabled=rerank_enabled,
        rerank_top_n=rerank_top_n,
        effective_k=len(chunks),
        score_kind=resolve_score_kind(
            rerank_applied=rerank_applied,
            retrieval_mode=retrieval_mode,
            hybrid_fts_active=hybrid_fts_active,
        ),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        indexed_chunk_count=indexed_chunk_count,
        hybrid_fts_active=hybrid_fts_active,
        rerank_applied=rerank_applied,
    )


def compute_retrieval_proxy_metrics(
    *,
    chunks: list[ChunkHit],
    merged_context: str,
    score_kind: ScoreKind,
) -> RetrievalProxyMetrics:
    """Compute retrieval-only quality proxies without ground-truth phrases."""
    effective_k = len(chunks)
    if not chunks:
        return RetrievalProxyMetrics(
            chunk_count=0,
            mean_chunk_score=0.0,
            max_chunk_score=0.0,
            context_length_chars=len(merged_context),
            score_kind=score_kind,
            effective_k=effective_k,
        )
    scores = [chunk.score for chunk in chunks]
    return RetrievalProxyMetrics(
        chunk_count=len(chunks),
        mean_chunk_score=round(sum(scores) / len(scores), 4),
        max_chunk_score=round(max(scores), 4),
        context_length_chars=len(merged_context),
        score_kind=score_kind,
        effective_k=effective_k,
    )
