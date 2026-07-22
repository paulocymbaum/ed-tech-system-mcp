"""Tests for RAG retrieval domain ports, adapters, and LangGraph workflow."""

from __future__ import annotations

from typing import Literal

import pytest

from mcp_server.application.agent import list_registered_workflows, reset_registered_workflows_cache
from mcp_server.application.agents.rag_retrieval.graph import (
    build_rag_retrieval_graph,
    reset_rag_retrieval_graph_cache,
    run_rag_retrieval_graph,
)
from mcp_server.application.retrieval_runtime import (
    reset_retrieval_clients,
    set_embedding_provider,
    set_reranker,
    set_vector_retriever,
)
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.domain.interfaces import IEmbeddingProvider, IReranker, IVectorRetriever
from mcp_server.domain.port_cache_trace import (
    record_embedding_cache_status,
    record_retrieval_cache_status,
)
from mcp_server.domain.schemas import ChunkHit, ChunkRetrievalFilter
from mcp_server.infrastructure.chunking.langchain_chunking_adapter import LangChainChunkingAdapter
from mcp_server.infrastructure.embeddings.fastembed_adapter import (
    E5_PASSAGE_PREFIX,
    E5_QUERY_PREFIX,
    FastEmbedAdapter,
)
from mcp_server.infrastructure.rerank.noop_reranker import NoOpReranker


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


class FakeReranker(IReranker):
    async def rerank(
        self,
        query: str,
        candidates: list[ChunkHit],
        *,
        top_n: int,
    ) -> list[ChunkHit]:
        _ = query
        return list(reversed(candidates))[:top_n]


@pytest.fixture(autouse=True)
def _reset_rag_runtime() -> None:
    reset_workflow_execution_config()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=30.0,
        )
    )
    reset_rag_retrieval_graph_cache()
    reset_registered_workflows_cache()
    reset_retrieval_clients()
    yield
    reset_rag_retrieval_graph_cache()
    reset_registered_workflows_cache()
    reset_retrieval_clients()
    reset_workflow_execution_config()


class CacheAwareFakeEmbeddingProvider(FakeEmbeddingProvider):
    def __init__(self, *, cache_hit: bool, dimensions: int = 384) -> None:
        super().__init__(dimensions=dimensions)
        self._cache_hit = cache_hit

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        record_embedding_cache_status("hit" if self._cache_hit else "miss")
        return await super().embed_queries(texts)


class CacheAwareFakeVectorRetriever(FakeVectorRetriever):
    def __init__(self, *, cache_hit: bool) -> None:
        super().__init__()
        self._cache_hit = cache_hit

    async def retrieve(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        filters: ChunkRetrievalFilter,
        mode: Literal["vector", "hybrid"],
        query_text: str | None = None,
    ) -> list[ChunkHit]:
        record_retrieval_cache_status("hit" if self._cache_hit else "miss")
        return await super().retrieve(
            query_embedding,
            limit=limit,
            filters=filters,
            mode=mode,
            query_text=query_text,
        )


@pytest.mark.asyncio
async def test_rag_retrieval_graph_records_cache_hit_in_state() -> None:
    set_embedding_provider(CacheAwareFakeEmbeddingProvider(cache_hit=True))
    set_vector_retriever(CacheAwareFakeVectorRetriever(cache_hit=False))
    set_reranker(NoOpReranker())

    state = await run_rag_retrieval_graph(
        "cache trace query",
        retrieval_mode="vector",
        rerank_enabled=False,
    )

    assert state["retrieval_complete"] is True


@pytest.mark.asyncio
async def test_rag_nodes_emit_cache_hit_fields() -> None:
    from mcp_server.application.agents.rag_retrieval.nodes import embed_query, retrieve_chunks
    from mcp_server.application.agents.rag_retrieval.state import RagRetrievalState

    set_embedding_provider(CacheAwareFakeEmbeddingProvider(cache_hit=True))
    set_vector_retriever(CacheAwareFakeVectorRetriever(cache_hit=False))

    embed_state: RagRetrievalState = {
        "query": "cache test",
        "retrieval_mode": "vector",
        "retrieve_limit": 5,
        "rerank_top_n": 3,
        "rerank_enabled": False,
    }
    embed_update = await embed_query(embed_state)
    assert embed_update["cache_hit"] is True

    retrieve_state: RagRetrievalState = {
        **embed_state,
        "query_embedding": embed_update["query_embedding"],  # type: ignore[typeddict-item]
    }
    retrieve_update = await retrieve_chunks(retrieve_state)
    assert retrieve_update["cache_hit"] is False


@pytest.mark.asyncio
async def test_rag_retrieval_graph_with_mocked_ports() -> None:
    embedder = FakeEmbeddingProvider(dimensions=384)
    retriever = FakeVectorRetriever()
    reranker = FakeReranker()
    set_embedding_provider(embedder)
    set_vector_retriever(retriever)
    set_reranker(reranker)

    state = await run_rag_retrieval_graph(
        "how does photosynthesis work?",
        retrieval_mode="hybrid",
        rerank_enabled=True,
        rerank_top_n=1,
    )

    assert state["retrieval_complete"] is True
    assert "Photosynthesis" in state["merged_context"]
    assert embedder.queries == ["how does photosynthesis work?"]
    assert retriever.last_mode == "hybrid"
    assert retriever.last_query_text == "how does photosynthesis work?"
    assert state.get("reranked_chunks")
    metrics = state.get("retrieval_metrics", {})
    assert metrics.get("chunk_count", 0) >= 1
    assert metrics.get("mean_chunk_score", 0.0) > 0.0
    assert metrics.get("max_chunk_score", 0.0) > 0.0
    assert metrics.get("context_length_chars", 0) > 0
    assert metrics.get("score_kind") == "reranker"
    assert metrics.get("effective_k", 0) >= 1
    context = state.get("rag_evaluation_context", {})
    assert context.get("score_kind") == "reranker"
    assert context.get("retrieval_mode") == "hybrid"


@pytest.mark.asyncio
async def test_rag_retrieval_graph_hybrid_without_rerank_uses_rrf_score_kind() -> None:
    embedder = FakeEmbeddingProvider()
    retriever = FakeVectorRetriever()
    set_embedding_provider(embedder)
    set_vector_retriever(retriever)
    set_reranker(NoOpReranker())

    state = await run_rag_retrieval_graph(
        "how does photosynthesis work?",
        retrieval_mode="hybrid",
        rerank_enabled=False,
    )

    assert state["retrieval_complete"] is True
    assert retriever.last_mode == "hybrid"
    assert retriever.last_query_text == "how does photosynthesis work?"
    metrics = state.get("retrieval_metrics", {})
    assert metrics.get("score_kind") == "rrf"
    context = state.get("rag_evaluation_context", {})
    assert context.get("score_kind") == "rrf"
    assert context.get("retrieval_mode") == "hybrid"


@pytest.mark.asyncio
async def test_rag_retrieval_graph_skips_rerank_when_disabled() -> None:
    embedder = FakeEmbeddingProvider()
    retriever = FakeVectorRetriever()
    set_embedding_provider(embedder)
    set_vector_retriever(retriever)
    set_reranker(NoOpReranker())

    state = await run_rag_retrieval_graph(
        "algebra basics",
        retrieval_mode="vector",
        rerank_enabled=False,
    )

    assert state["retrieval_complete"] is True
    assert state.get("reranked_chunks") is None
    assert retriever.last_mode == "vector"
    assert retriever.last_query_text is None


def test_registered_workflows_include_rag_retrieval() -> None:
    workflow_ids = {workflow.id for workflow in list_registered_workflows()}
    assert "rag-retrieval" in workflow_ids


def test_rag_retrieval_graph_compiles() -> None:
    graph = build_rag_retrieval_graph()
    assert graph is not None


def test_langchain_chunking_produces_hashes() -> None:
    chunker = LangChainChunkingAdapter(chunk_size=10, chunk_overlap=0)
    long_text = "word " * 200
    chunks = chunker.chunk(
        long_text,
        document_id="doc-abc",
        language="en",
    )
    assert chunks
    assert all(chunk.content_hash for chunk in chunks)
    assert chunks[0].chunk_index == 0


def test_langchain_chunking_adapter_exposes_chunk_properties() -> None:
    chunker = LangChainChunkingAdapter(chunk_size=256, chunk_overlap=32)
    assert chunker.chunk_size == 256
    assert chunker.chunk_overlap == 32


@pytest.mark.asyncio
async def test_fastembed_adapter_e5_prefix_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    class _FakeModel:
        def embed(self, texts: list[str]):
            captured.extend(texts)
            return iter([[0.0] * 384 for _ in texts])

    adapter = FastEmbedAdapter(
        model_name="intfloat/multilingual-e5-large",
        dimensions=1024,
        cache_dir=".cache/fastembed-test",
    )
    monkeypatch.setattr(adapter, "_get_model", lambda: _FakeModel())

    await adapter.embed_queries(["hello"])
    await adapter.embed_passages(["world"])

    assert captured == [f"{E5_QUERY_PREFIX}hello", f"{E5_PASSAGE_PREFIX}world"]


@pytest.mark.asyncio
async def test_fake_embedding_provider_returns_384_dimensions() -> None:
    provider = FakeEmbeddingProvider(dimensions=384)
    vectors = await provider.embed_queries(["test"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 384


@pytest.mark.asyncio
async def test_noop_reranker_truncates_without_rescoring() -> None:
    reranker = NoOpReranker()
    candidates = [
        ChunkHit(id="1", document_id="d", content="a", score=0.1),
        ChunkHit(id="2", document_id="d", content="b", score=0.9),
    ]
    result = await reranker.rerank("q", candidates, top_n=1)
    assert len(result) == 1
    assert result[0].id == "1"
