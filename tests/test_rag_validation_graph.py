"""Tests for the RAG validation LangGraph workflow."""

from __future__ import annotations

import pytest

from mcp_server.application.agent import list_registered_workflows, reset_registered_workflows_cache
from mcp_server.application.agents.rag_validation.fixture import (
    DEFAULT_CORPUS_PATH,
    FIXTURE_DOCUMENT_ID,
    load_expected_phrases,
)
from mcp_server.application.agents.rag_validation.graph import (
    build_rag_validation_graph,
    reset_rag_validation_graph_cache,
    run_rag_validation_graph,
)
from mcp_server.application.retrieval_runtime import (
    reset_retrieval_clients,
    set_chunking_strategy,
    set_embedding_provider,
    set_reranker,
    set_vector_index_writer,
    set_vector_retriever,
)
from mcp_server.application.token_counting_runtime import reset_token_counter, set_token_counter
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.infrastructure.rerank.noop_reranker import NoOpReranker
from mcp_server.infrastructure.token_counting.tiktoken_counter import TiktokenTokenCounter
from rag_fakes import (
    FakeChunkingStrategy,
    FakeEmbeddingProvider,
    FixtureAwareRetriever,
    RecordingIndexWriter,
)


@pytest.fixture(autouse=True)
def _reset_rag_validation_runtime() -> None:
    reset_workflow_execution_config()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=30.0,
        )
    )
    reset_rag_validation_graph_cache()
    reset_registered_workflows_cache()
    reset_retrieval_clients()
    reset_token_counter()
    set_token_counter(TiktokenTokenCounter())
    yield
    reset_rag_validation_graph_cache()
    reset_registered_workflows_cache()
    reset_retrieval_clients()
    reset_workflow_execution_config()
    reset_token_counter()


def test_bundled_fixture_files_exist() -> None:
    assert DEFAULT_CORPUS_PATH.is_file()
    phrases = load_expected_phrases()
    assert "chlorophyll" in phrases


def test_registered_workflows_include_rag_validation() -> None:
    workflow_ids = {workflow.id for workflow in list_registered_workflows()}
    assert "rag-validation" in workflow_ids


def test_rag_validation_graph_compiles() -> None:
    graph = build_rag_validation_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_rag_validation_graph_uses_inline_document_text() -> None:
    writer = RecordingIndexWriter()
    retriever = FixtureAwareRetriever(writer)
    set_chunking_strategy(FakeChunkingStrategy())
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(retriever)
    set_reranker(NoOpReranker())

    custom_text = (
        "Photosynthesis uses chlorophyll in light-dependent reactions to produce glucose for plants."
    )
    state = await run_rag_validation_graph(
        "How does photosynthesis work?",
        document_text=custom_text,
        document_title="Inline test doc",
        expected_phrases=["chlorophyll", "glucose"],
        retrieval_mode="vector",
        rerank_enabled=False,
    )

    assert state["document_source"] == "inline"
    assert state["document_title"] == "Inline test doc"
    assert state["validation_passed"] is True
    assert custom_text[:40] in writer.chunks[0].content


@pytest.mark.asyncio
async def test_rag_validation_retrieve_limit_changes_phrase_coverage() -> None:
    from mcp_server.application.agents.rag_validation.fixture import load_default_document_text

    writer = RecordingIndexWriter()
    retriever = FixtureAwareRetriever(writer)
    set_chunking_strategy(FakeChunkingStrategy())
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(retriever)
    set_reranker(NoOpReranker())

    document_text = load_default_document_text()
    query = "How does photosynthesis convert light energy?"

    state_low = await run_rag_validation_graph(
        query,
        document_text=document_text,
        retrieval_mode="vector",
        retrieve_limit=1,
        rerank_enabled=False,
    )
    state_high = await run_rag_validation_graph(
        query,
        document_text=document_text,
        retrieval_mode="vector",
        retrieve_limit=4,
        rerank_enabled=False,
    )

    low_coverage = state_low["rag_benchmarks"]["phrase_coverage"]
    high_coverage = state_high["rag_benchmarks"]["phrase_coverage"]
    assert state_low["indexed_chunk_count"] >= 3
    assert low_coverage < high_coverage
    assert high_coverage == 1.0
    assert state_low["rag_evaluation_context"]["effective_k"] == 1
    assert state_high["rag_evaluation_context"]["effective_k"] >= 3


@pytest.mark.asyncio
async def test_rag_validation_graph_skips_reindex_when_content_hash_matches() -> None:
    class _HashAwareWriter(RecordingIndexWriter):
        def __init__(self) -> None:
            super().__init__()
            self.content_hash = "stale"

        async def get_document_content_hash(self, document_id: str) -> str | None:
            _ = document_id
            return self.content_hash

        async def upsert_document(self, **kwargs: object) -> None:
            content_hash = kwargs.get("content_hash")
            if isinstance(content_hash, str):
                self.content_hash = content_hash

    from mcp_server.application.agents.rag_validation.fixture import load_default_document_text
    import hashlib

    writer = _HashAwareWriter()
    document_text = load_default_document_text()
    writer.content_hash = hashlib.sha256(document_text.strip().encode("utf-8")).hexdigest()
    retriever = FixtureAwareRetriever(writer)
    set_chunking_strategy(FakeChunkingStrategy())
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(retriever)
    set_reranker(NoOpReranker())

    state = await run_rag_validation_graph(
        "How does photosynthesis convert light energy?",
        document_text=document_text,
        retrieval_mode="vector",
        rerank_enabled=False,
    )

    assert state.get("index_skipped") is True
    assert state["index_complete"] is True
    assert len(writer.chunks) == 0


@pytest.mark.asyncio
async def test_rag_validation_graph_end_to_end_with_mocked_ports() -> None:
    writer = RecordingIndexWriter()
    retriever = FixtureAwareRetriever(writer)
    set_chunking_strategy(FakeChunkingStrategy(chunk_size=512, chunk_overlap=64))
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(retriever)
    set_reranker(NoOpReranker())

    state = await run_rag_validation_graph(
        "How does photosynthesis convert light energy?",
        retrieval_mode="vector",
        rerank_enabled=False,
    )

    assert state["index_complete"] is True
    assert state["indexed_chunk_count"] >= 1
    assert state["chunk_size"] == 512
    assert state["chunk_overlap"] == 64
    assert state["retrieval_complete"] is True
    assert state["validation_passed"] is True
    assert state["validation_errors"] == []
    assert "chlorophyll" in state["merged_context"].lower()
    assert writer.chunks[0].document_id == FIXTURE_DOCUMENT_ID
    benchmarks = state.get("rag_benchmarks", {})
    assert benchmarks.get("phrase_coverage") == 1.0
    assert benchmarks.get("any_phrase_hit") == 1.0
    assert benchmarks.get("matched_phrase_count", 0) >= 1
    assert "chlorophyll" in state["matched_phrases"]
    assert state["missing_phrases"] == []
    evaluation_context = state.get("rag_evaluation_context", {})
    assert evaluation_context.get("score_kind") == "cosine"
    assert evaluation_context.get("retrieval_mode") == "vector"
    assert evaluation_context.get("chunk_size") == 512
    assert evaluation_context.get("chunk_overlap") == 64
