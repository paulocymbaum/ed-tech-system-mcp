"""Compile and run the RAG validation LangGraph workflow."""

from __future__ import annotations

from typing import cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from mcp_server.application.agents.rag_retrieval.nodes import (
    embed_query,
    merge_context,
    rerank_chunks,
    retrieve_chunks,
    route_after_retrieve,
)
from mcp_server.application.agents.rag_validation.fixture import DEFAULT_QUERY
from mcp_server.application.agents.rag_validation.nodes import (
    index_document,
    load_document,
    validate_retrieval,
)
from mcp_server.application.agents.rag_validation.state import RagValidationState
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)

RagValidationGraph = CompiledStateGraph[RagValidationState, RagValidationState, RagValidationState]


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def _read_node_retry_policy() -> RetryPolicy:
    return RetryPolicy(max_attempts=2)


def _node_timeout_seconds() -> float:
    return _workflow_runtime_config().agent_node_timeout_seconds


def _rerank_node_timeout_seconds() -> float:
    """Rerank may download ONNX weights on first run; allow extra time."""
    base = _node_timeout_seconds()
    return max(base * 3.0, 180.0)


def build_rag_validation_graph() -> RagValidationGraph:
    """Build load document → index → embed → retrieve → [rerank] → merge → validate."""
    graph: StateGraph[RagValidationState, RagValidationState, RagValidationState] = StateGraph(
        RagValidationState
    )
    read_retry_policy = _read_node_retry_policy()
    node_timeout = _node_timeout_seconds()

    graph.add_node(
        "load_document",
        load_document,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "index_document",
        index_document,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "embed_query",
        embed_query,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "retrieve_chunks",
        retrieve_chunks,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "rerank_chunks",
        rerank_chunks,
        retry_policy=RetryPolicy(max_attempts=1),
        timeout=_rerank_node_timeout_seconds(),
    )
    graph.add_node(
        "merge_context",
        merge_context,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "validate_retrieval",
        validate_retrieval,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )

    graph.add_edge(START, "load_document")
    graph.add_edge("load_document", "index_document")
    graph.add_edge("index_document", "embed_query")
    graph.add_edge("embed_query", "retrieve_chunks")
    graph.add_conditional_edges("retrieve_chunks", route_after_retrieve)
    graph.add_edge("rerank_chunks", "merge_context")
    graph.add_edge("merge_context", "validate_retrieval")
    graph.add_edge("validate_retrieval", END)

    return graph.compile()


_COMPILED_GRAPH: RagValidationGraph | None = None


def get_rag_validation_graph() -> RagValidationGraph:
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_rag_validation_graph()
    return _COMPILED_GRAPH


def reset_rag_validation_graph_cache() -> None:
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def initial_rag_validation_state(
    query: str | None = None,
    *,
    fixture_path: str | None = None,
    document_text: str | None = None,
    document_title: str | None = None,
    expected_phrases: list[str] | None = None,
    retrieval_mode: str = "vector",
    retrieve_limit: int = 10,
    rerank_top_n: int = 6,
    rerank_enabled: bool = False,
    course_id: str | None = None,
    tags: list[str] | None = None,
    language: str | None = "en",
) -> RagValidationState:
    state: RagValidationState = {
        "query": query or DEFAULT_QUERY,
        "retrieval_mode": "hybrid" if retrieval_mode == "hybrid" else "vector",
        "retrieve_limit": retrieve_limit,
        "rerank_top_n": rerank_top_n,
        "rerank_enabled": rerank_enabled,
        "retrieval_complete": False,
        "index_complete": False,
        "validation_passed": False,
        "validation_errors": [],
    }
    if fixture_path is not None:
        state["fixture_path"] = fixture_path
    if document_text is not None:
        state["document_text"] = document_text
    if document_title is not None:
        state["document_title"] = document_title
    if expected_phrases is not None:
        state["expected_phrases"] = expected_phrases
    if course_id is not None:
        state["course_id"] = course_id
    if tags is not None:
        state["tags"] = tags
    if language is not None:
        state["language"] = language
    return state


async def run_rag_validation_graph(
    query: str | None = None,
    **kwargs: object,
) -> RagValidationState:
    from mcp_server.application.agent import ainvoke_with_workflow_timeout

    graph = get_rag_validation_graph()
    state = initial_rag_validation_state(query, **kwargs)  # type: ignore[arg-type]
    result = await ainvoke_with_workflow_timeout(graph, state)
    return cast(RagValidationState, result)
