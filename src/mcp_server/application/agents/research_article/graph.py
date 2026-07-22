"""Compile and run the research-article LangGraph workflow."""

from __future__ import annotations

from typing import cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from mcp_server.application.agents.research_article.nodes import (
    agent_plan_research,
    dispatch_parallel_tools,
    merge_context,
    tool_search_tavily,
    tool_search_youtube,
    write_article,
)
from mcp_server.application.agents.research_article.state import ResearchArticleState
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)

ResearchArticleGraph = CompiledStateGraph[
    ResearchArticleState, ResearchArticleState, ResearchArticleState
]


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def _node_retry_policy() -> RetryPolicy:
    config = _workflow_runtime_config()
    max_attempts = max(config.node_retries + 1, 1)
    return RetryPolicy(max_attempts=max_attempts)


def _read_node_retry_policy() -> RetryPolicy:
    return RetryPolicy(max_attempts=2)


def _node_timeout_seconds() -> float:
    return _workflow_runtime_config().agent_node_timeout_seconds


def build_research_article_graph() -> ResearchArticleGraph:
    """Build the research → parallel async tools → merge → article LangGraph."""
    graph: StateGraph[ResearchArticleState, ResearchArticleState, ResearchArticleState] = (
        StateGraph(ResearchArticleState)
    )
    llm_retry_policy = _node_retry_policy()
    read_retry_policy = _read_node_retry_policy()
    node_timeout = _node_timeout_seconds()

    graph.add_node(
        "agent_plan_research",
        agent_plan_research,
        retry_policy=llm_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "tool_search_tavily",
        tool_search_tavily,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node(
        "tool_search_youtube",
        tool_search_youtube,
        retry_policy=read_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node("merge_context", merge_context, defer=True, timeout=node_timeout)
    graph.add_node(
        "write_article",
        write_article,
        retry_policy=llm_retry_policy,
        timeout=node_timeout,
    )

    graph.add_edge(START, "agent_plan_research")
    graph.add_conditional_edges("agent_plan_research", dispatch_parallel_tools)
    graph.add_edge("tool_search_tavily", "merge_context")
    graph.add_edge("tool_search_youtube", "merge_context")
    graph.add_edge("merge_context", "write_article")
    graph.add_edge("write_article", END)

    return graph.compile()


_COMPILED_GRAPH: ResearchArticleGraph | None = None


def get_research_article_graph() -> ResearchArticleGraph:
    """Return the memoized research-article graph."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_research_article_graph()
    return _COMPILED_GRAPH


def reset_research_article_graph_cache() -> None:
    """Clear the memoized research-article graph (for tests)."""
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def initial_research_article_state(
    query: str,
    *,
    max_web_results: int = 5,
    max_video_results: int = 3,
) -> ResearchArticleState:
    """Build the initial graph state for research-article generation."""
    return ResearchArticleState(
        query=query,
        max_web_results=max_web_results,
        max_video_results=max_video_results,
        generation_complete=False,
    )


async def run_research_article_graph(
    query: str,
    *,
    max_web_results: int = 5,
    max_video_results: int = 3,
    config: RunnableConfig | None = None,
) -> ResearchArticleState:
    """Run the research-article graph with workflow timeout enforcement."""
    from mcp_server.application.agent import ainvoke_with_workflow_timeout

    graph = get_research_article_graph()
    state = initial_research_article_state(
        query,
        max_web_results=max_web_results,
        max_video_results=max_video_results,
    )
    result = await ainvoke_with_workflow_timeout(graph, state, config=config)
    return cast(ResearchArticleState, result)
