"""Compile and run the RAG retrieval LangGraph workflow."""

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
from mcp_server.application.agents.rag_retrieval.state import RagRetrievalState
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)

RagRetrievalGraph = CompiledStateGraph[RagRetrievalState, RagRetrievalState, RagRetrievalState]


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


def build_rag_retrieval_graph() -> RagRetrievalGraph:
    """Build embed → retrieve → [rerank] → merge LangGraph."""
    graph: StateGraph[RagRetrievalState, RagRetrievalState, RagRetrievalState] = StateGraph(
        RagRetrievalState
    )
    read_retry_policy = _read_node_retry_policy()
    node_timeout = _node_timeout_seconds()

    graph.add_node("embed_query", embed_query, retry_policy=read_retry_policy, timeout=node_timeout)
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

    graph.add_edge(START, "embed_query")
    graph.add_edge("embed_query", "retrieve_chunks")
    graph.add_conditional_edges("retrieve_chunks", route_after_retrieve)
    graph.add_edge("rerank_chunks", "merge_context")
    graph.add_edge("merge_context", END)

    return graph.compile()


_COMPILED_GRAPH: RagRetrievalGraph | None = None


def get_rag_retrieval_graph() -> RagRetrievalGraph:
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_rag_retrieval_graph()
    return _COMPILED_GRAPH


def reset_rag_retrieval_graph_cache() -> None:
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def initial_rag_retrieval_state(
    query: str,
    *,
    retrieval_mode: str = "hybrid",
    retrieve_limit: int = 20,
    rerank_top_n: int = 6,
    rerank_enabled: bool = False,
    tenant_id: str | None = None,
    course_id: str | None = None,
    tags: list[str] | None = None,
    language: str | None = None,
) -> RagRetrievalState:
    state: RagRetrievalState = {
        "query": query,
        "retrieval_mode": "hybrid" if retrieval_mode == "hybrid" else "vector",
        "retrieve_limit": retrieve_limit,
        "rerank_top_n": rerank_top_n,
        "rerank_enabled": rerank_enabled,
        "retrieval_complete": False,
    }
    if tenant_id is not None:
        state["tenant_id"] = tenant_id
    if course_id is not None:
        state["course_id"] = course_id
    if tags is not None:
        state["tags"] = tags
    if language is not None:
        state["language"] = language
    return state


async def run_rag_retrieval_graph(
    query: str,
    *,
    retrieval_mode: str = "hybrid",
    retrieve_limit: int = 20,
    rerank_top_n: int = 6,
    rerank_enabled: bool = False,
    tenant_id: str | None = None,
    course_id: str | None = None,
    tags: list[str] | None = None,
    language: str | None = None,
) -> RagRetrievalState:
    from mcp_server.application.agent import ainvoke_with_workflow_timeout

    graph = get_rag_retrieval_graph()
    state = initial_rag_retrieval_state(
        query,
        retrieval_mode=retrieval_mode,
        retrieve_limit=retrieve_limit,
        rerank_top_n=rerank_top_n,
        rerank_enabled=rerank_enabled,
        tenant_id=tenant_id,
        course_id=course_id,
        tags=tags,
        language=language,
    )
    result = await ainvoke_with_workflow_timeout(graph, state)
    return cast(RagRetrievalState, result)
