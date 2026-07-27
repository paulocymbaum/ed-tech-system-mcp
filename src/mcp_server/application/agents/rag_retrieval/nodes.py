"""LangGraph nodes for semantic RAG retrieval."""

from __future__ import annotations

import time

from mcp_server.application.agents.rag_retrieval.state import RagRetrievalState
from mcp_server.application.retrieval_runtime import (
    get_embedding_provider,
    get_reranker,
    get_vector_retriever,
)
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.interfaces import IEmbeddingProvider, IReranker, IVectorRetriever
from mcp_server.domain.port_cache_trace import (
    consume_embedding_cache_hit,
    consume_retrieval_cache_hit,
)
from mcp_server.domain.rag_benchmarks import (
    build_rag_evaluation_context,
    compute_retrieval_proxy_metrics,
    resolve_score_kind,
)
from mcp_server.domain.schemas import ChunkRetrievalFilter


def _require_embedding_provider() -> IEmbeddingProvider:
    provider = get_embedding_provider()
    if provider is None:
        raise ResourceNotFoundError("Embedding provider has not been initialized")
    return provider


def _require_vector_retriever() -> IVectorRetriever:
    retriever = get_vector_retriever()
    if retriever is None:
        raise ResourceNotFoundError("Vector retriever has not been initialized")
    return retriever


def _require_reranker() -> IReranker:
    reranker = get_reranker()
    if reranker is None:
        raise ResourceNotFoundError("Reranker has not been initialized")
    return reranker


def _build_filters(state: RagRetrievalState) -> ChunkRetrievalFilter:
    return ChunkRetrievalFilter(
        course_id=state.get("course_id"),
        tags=state.get("tags"),
        language=state.get("language"),
    )


async def embed_query(state: RagRetrievalState) -> dict[str, object]:
    """Embed the user query via IEmbeddingProvider.embed_queries."""
    started = time.perf_counter()
    provider = _require_embedding_provider()
    vectors = await provider.embed_queries([state["query"]])
    if not vectors:
        msg = "Embedding provider returned no vectors for query"
        raise ResourceNotFoundError(msg)
    latency_ms = int((time.perf_counter() - started) * 1000)
    update: dict[str, object] = {
        "query_embedding": vectors[0],
        "candidate_count": 0,
        "latency_ms": latency_ms,
    }
    cache_hit = consume_embedding_cache_hit()
    if cache_hit is not None:
        update["cache_hit"] = cache_hit
    return update


async def retrieve_chunks(state: RagRetrievalState) -> dict[str, object]:
    """Retrieve candidate chunks from the vector index."""
    started = time.perf_counter()
    retriever = _require_vector_retriever()
    query_embedding = state.get("query_embedding")
    if query_embedding is None:
        msg = "query_embedding is required before retrieve_chunks"
        raise ResourceNotFoundError(msg)

    mode = state["retrieval_mode"]
    chunks = await retriever.retrieve(
        query_embedding,
        limit=state["retrieve_limit"],
        filters=_build_filters(state),
        mode=mode,
        query_text=state["query"] if mode == "hybrid" else None,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    hybrid_fts_active = mode == "hybrid" and retriever.supports_hybrid_fts
    update: dict[str, object] = {
        "retrieved_chunks": chunks,
        "candidate_count": len(chunks),
        "retrieval_mode": mode,
        "latency_ms": latency_ms,
        "hybrid_fts_active": hybrid_fts_active,
    }
    cache_hit = consume_retrieval_cache_hit()
    if cache_hit is not None:
        update["cache_hit"] = cache_hit
    return update


async def rerank_chunks(state: RagRetrievalState) -> dict[str, object]:
    """Re-rank retrieved chunks when rerank_enabled is true."""
    started = time.perf_counter()
    reranker = _require_reranker()
    candidates = state.get("retrieved_chunks", [])
    reranked = await reranker.rerank(
        state["query"],
        candidates,
        top_n=state["rerank_top_n"],
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {
        "reranked_chunks": reranked,
        "rerank_applied": not reranker.is_pass_through,
        "candidate_count": len(reranked),
        "latency_ms": latency_ms,
    }


def route_after_retrieve(state: RagRetrievalState) -> str:
    """Conditional edge: rerank or skip to merge."""
    if state.get("rerank_enabled"):
        return "rerank_chunks"
    return "merge_context"


async def merge_context(state: RagRetrievalState) -> dict[str, object]:
    """Format top chunks into a single context block for downstream LLM use."""
    reranked = state.get("reranked_chunks") is not None
    rerank_applied = reranked and bool(state.get("rerank_applied"))
    hybrid_fts_active = bool(state.get("hybrid_fts_active"))
    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks", [])
    lines = [
        (
            f"[{index + 1}] (score={chunk.score:.3f}) "
            f"{chunk.title or chunk.document_id}\n{chunk.content}"
        )
        for index, chunk in enumerate(chunks)
    ]
    merged = "\n\n".join(lines) if lines else "(no chunks retrieved)"
    score_kind = resolve_score_kind(
        rerank_applied=rerank_applied,
        retrieval_mode=state["retrieval_mode"],
        hybrid_fts_active=hybrid_fts_active,
    )
    retrieval_metrics = compute_retrieval_proxy_metrics(
        chunks=chunks,
        merged_context=merged,
        score_kind=score_kind,
    )
    evaluation_context = build_rag_evaluation_context(
        retrieval_mode=state["retrieval_mode"],
        retrieve_limit=state["retrieve_limit"],
        rerank_enabled=state["rerank_enabled"],
        rerank_top_n=state["rerank_top_n"],
        chunks=chunks,
        rerank_applied=rerank_applied,
        hybrid_fts_active=hybrid_fts_active,
        chunk_size=state.get("chunk_size"),
        chunk_overlap=state.get("chunk_overlap"),
        indexed_chunk_count=state.get("indexed_chunk_count"),
    )
    return {
        "merged_context": merged,
        "retrieval_complete": True,
        "candidate_count": len(chunks),
        "retrieval_metrics": retrieval_metrics.as_dict(),
        "rag_evaluation_context": evaluation_context.as_dict(),
    }
