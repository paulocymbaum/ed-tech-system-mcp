"""State for the RAG retrieval LangGraph workflow."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from mcp_server.domain.schemas import ChunkHit


class RagRetrievalState(TypedDict):
    """State carried through embed → retrieve → [rerank] → merge."""

    query: str
    retrieval_mode: Literal["vector", "hybrid"]
    retrieve_limit: int
    rerank_top_n: int
    rerank_enabled: bool
    tenant_id: NotRequired[str]
    course_id: NotRequired[str]
    tags: NotRequired[list[str]]
    language: NotRequired[str]
    query_embedding: NotRequired[list[float]]
    retrieved_chunks: NotRequired[list[ChunkHit]]
    reranked_chunks: NotRequired[list[ChunkHit]]
    merged_context: NotRequired[str]
    retrieval_complete: bool
    candidate_count: NotRequired[int]
    latency_ms: NotRequired[int]
    cache_hit: NotRequired[bool]
    retrieval_metrics: NotRequired[dict[str, float | int | str]]
    rag_evaluation_context: NotRequired[dict[str, str | int | bool | None]]
    chunk_size: NotRequired[int]
    chunk_overlap: NotRequired[int]
    indexed_chunk_count: NotRequired[int]
    hybrid_fts_active: NotRequired[bool]
    rerank_applied: NotRequired[bool]
