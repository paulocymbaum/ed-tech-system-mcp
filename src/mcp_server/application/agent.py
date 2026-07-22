"""LangChain agent and LangGraph workflow definitions."""

from __future__ import annotations

import asyncio
from typing import Any, NotRequired, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from mcp_server.application.agents.content_generation.graph import (
    get_content_generation_graph,
    reset_content_generation_graph_cache,
)
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)
from mcp_server.application.workflow_graph import RegisteredWorkflow
from mcp_server.application.workflow_runtime import get_document_video_workflow
from mcp_server.application.workflows import DocumentVideoWorkflow
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.schemas import DocumentHit, VideoResult

DocumentVideoGraph = CompiledStateGraph[
    "DocumentVideoState", "DocumentVideoState", "DocumentVideoState"
]


class DocumentVideoState(TypedDict):
    """State carried through the document + video discovery graph."""

    query: str
    document_limit: int
    video_limit: int
    search_terms: str
    document_count: int
    video_count: int
    documents: NotRequired[list[DocumentHit]]
    videos: NotRequired[list[VideoResult]]


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    """Return runtime config, falling back to repo-root defaults when not initialized."""
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def _node_retry_policy() -> RetryPolicy:
    config = _workflow_runtime_config()
    max_attempts = max(config.node_retries + 1, 1)
    return RetryPolicy(max_attempts=max_attempts)


def _read_node_retry_policy() -> RetryPolicy:
    """Lower retry budget for idempotent read-only external port calls."""
    return RetryPolicy(max_attempts=2)


def _node_timeout_seconds() -> float:
    return _workflow_runtime_config().agent_node_timeout_seconds


def _require_workflow() -> DocumentVideoWorkflow:
    workflow = get_document_video_workflow()
    if workflow is None:
        raise ResourceNotFoundError("Document video workflow has not been initialized")
    return workflow


async def _fetch_documents(state: DocumentVideoState) -> dict[str, object]:
    workflow = _require_workflow()
    documents = await workflow.fetch_documents(state["query"], state["document_limit"])
    return {
        "documents": documents,
        "document_count": len(documents),
    }


async def _derive_search_terms(state: DocumentVideoState) -> dict[str, str]:
    workflow = _require_workflow()
    documents = state.get("documents", [])
    search_terms = workflow.derive_search_terms(state["query"], documents)
    return {"search_terms": search_terms}


async def _search_videos(state: DocumentVideoState) -> dict[str, object]:
    workflow = _require_workflow()
    videos = await workflow.search_videos(state["search_terms"], state["video_limit"])
    return {
        "videos": videos,
        "video_count": len(videos),
    }


async def _merge_results(state: DocumentVideoState) -> dict[str, int]:
    return {
        "document_count": state.get("document_count", 0),
        "video_count": state.get("video_count", 0),
    }


def build_document_video_graph() -> DocumentVideoGraph:
    """Build the LangGraph for document retrieval enriched with video discovery.

    Nodes run fetch → derive → search sequentially so each step is visible in
    graph traces and the local workflow UI. BL-010 parallel I/O applies only to
    ``DocumentVideoWorkflow.retrieve_with_videos`` (MCP ``find_documents``), not
    this graph path.
    """
    graph: StateGraph[DocumentVideoState, DocumentVideoState, DocumentVideoState] = StateGraph(
        DocumentVideoState
    )
    read_retry_policy = _read_node_retry_policy()
    node_timeout = _node_timeout_seconds()

    graph.add_node(
        "fetch_documents",
        _fetch_documents,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "derive_search_terms",
        _derive_search_terms,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "search_videos",
        _search_videos,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "merge_results",
        _merge_results,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )

    graph.add_edge(START, "fetch_documents")
    graph.add_edge("fetch_documents", "derive_search_terms")
    graph.add_edge("derive_search_terms", "search_videos")
    graph.add_edge("search_videos", "merge_results")
    graph.add_edge("merge_results", END)

    return graph.compile()


_COMPILED_GRAPH: DocumentVideoGraph | None = None


def _get_compiled_graph() -> DocumentVideoGraph:
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_document_video_graph()
    return _COMPILED_GRAPH


def reset_compiled_graph_cache() -> None:
    """Clear the memoized compiled graph (for tests)."""
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def create_agent() -> DocumentVideoGraph:
    """Return the primary LangGraph agent used by application workflows."""
    return build_document_video_graph()


def workflow_timeout_seconds() -> float:
    """Return the configured overall workflow execution timeout."""
    return _workflow_runtime_config().workflow_timeout_seconds


async def ainvoke_with_workflow_timeout(
    graph: CompiledStateGraph[Any, Any, Any],
    state: Any,
    *,
    config: RunnableConfig | None = None,
) -> Any:
    """Invoke a compiled graph with the configured workflow timeout."""
    result = await asyncio.wait_for(
        graph.ainvoke(state, config=config),
        timeout=workflow_timeout_seconds(),
    )
    return result


def initial_document_video_state(
    query: str,
    *,
    document_limit: int = 10,
    video_limit: int = 5,
) -> DocumentVideoState:
    """Build the initial graph state for document + video discovery."""
    return DocumentVideoState(
        query=query,
        document_limit=document_limit,
        video_limit=video_limit,
        search_terms=query,
        document_count=0,
        video_count=0,
    )


def get_document_video_graph() -> DocumentVideoGraph:
    """Return the memoized document-video graph."""
    return _get_compiled_graph()


async def run_document_video_graph(
    query: str,
    *,
    document_limit: int = 10,
    video_limit: int = 5,
) -> DocumentVideoState:
    """Run the document-video graph with workflow timeout enforcement.

    Executes the sequential LangGraph path. For optimistic parallel document/video
    I/O, use ``DocumentVideoWorkflow.retrieve_with_videos`` via MCP
    ``find_documents`` instead.
    """
    graph = _get_compiled_graph()
    state = initial_document_video_state(
        query,
        document_limit=document_limit,
        video_limit=video_limit,
    )
    return await ainvoke_with_workflow_timeout(graph, state)


_REGISTERED_WORKFLOWS: list[RegisteredWorkflow] | None = None


def _build_registered_workflows() -> list[RegisteredWorkflow]:
    return [
        RegisteredWorkflow(
            id="document-video-discovery",
            name="Document + Video Discovery",
            description=(
                "Retrieve educational documents, derive search terms from metadata, "
                "and discover complementary YouTube videos."
            ),
            graph=_get_compiled_graph(),
        ),
        RegisteredWorkflow(
            id="content-generation",
            name="Lesson → Quiz + PBL",
            description=(
                "Generate a structured lesson with Groq, then derive a quiz and "
                "problem-based learning project with validation retries and model fallback."
            ),
            graph=get_content_generation_graph(),
        ),
    ]


def list_registered_workflows() -> list[RegisteredWorkflow]:
    """Return all LangGraph workflows exposed to the local UI."""
    global _REGISTERED_WORKFLOWS
    if _REGISTERED_WORKFLOWS is None:
        _REGISTERED_WORKFLOWS = _build_registered_workflows()
    return _REGISTERED_WORKFLOWS


def reset_registered_workflows_cache() -> None:
    """Clear cached workflow list (for tests)."""
    global _REGISTERED_WORKFLOWS
    _REGISTERED_WORKFLOWS = None
    reset_compiled_graph_cache()
    reset_content_generation_graph_cache()
