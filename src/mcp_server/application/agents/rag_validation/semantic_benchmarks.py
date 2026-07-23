"""Embedding-based semantic benchmarks against a gold reference answer."""

from __future__ import annotations

from mcp_server.application.retrieval_runtime import get_embedding_provider
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.rag_benchmarks import (
    DEFAULT_GOLD_SEMANTIC_PRECISION_THRESHOLD,
    RagBenchmarkScores,
    compute_semantic_gold_benchmarks,
)
from mcp_server.domain.schemas import ChunkHit


def _coerce_chunk_hits(chunks: object) -> list[ChunkHit]:
    if not isinstance(chunks, list):
        return []
    hits: list[ChunkHit] = []
    for item in chunks:
        if isinstance(item, ChunkHit):
            hits.append(item)
        elif isinstance(item, dict):
            hits.append(ChunkHit.model_validate(item))
    return hits


async def enrich_benchmarks_with_gold_semantic(
    benchmarks: RagBenchmarkScores,
    *,
    gold_answer: str,
    chunks: object,
    relevance_threshold: float = DEFAULT_GOLD_SEMANTIC_PRECISION_THRESHOLD,
) -> RagBenchmarkScores:
    """Attach semantic relevance and precision metrics using the wired embedder."""
    normalized_answer = gold_answer.strip()
    chunk_hits = _coerce_chunk_hits(chunks)
    if not normalized_answer or not chunk_hits:
        return benchmarks

    provider = get_embedding_provider()
    if provider is None:
        raise ResourceNotFoundError("Embedding provider has not been initialized")

    gold_vectors = await provider.embed_queries([normalized_answer])
    if not gold_vectors:
        return benchmarks

    passage_vectors = await provider.embed_passages([chunk.content for chunk in chunk_hits])
    if len(passage_vectors) != len(chunk_hits):
        return benchmarks

    max_relevance, mean_relevance, precision, rank_reciprocal = compute_semantic_gold_benchmarks(
        gold_embedding=gold_vectors[0],
        chunk_embeddings=passage_vectors,
        relevance_threshold=relevance_threshold,
    )
    return benchmarks.with_semantic_gold_scores(
        gold_semantic_relevance=max_relevance,
        mean_gold_semantic_relevance=mean_relevance,
        gold_semantic_precision=precision,
        gold_semantic_rank_reciprocal=rank_reciprocal,
    )
