"""LangGraph workflow for Tavily web search."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from mcp_server.application.integration_runtime import get_search_client
from mcp_server.domain.exceptions import ResourceNotFoundError

TavilySearchGraph = CompiledStateGraph[
    "TavilySearchState", "TavilySearchState", "TavilySearchState"
]


class TavilySearchState(TypedDict):
    """State carried through the Tavily search graph."""

    query: str
    max_results: int
    results: NotRequired[list[str]]
    result_count: int


def _require_search_client():
    client = get_search_client()
    if client is None:
        raise ResourceNotFoundError("Search client has not been initialized")
    return client


async def _run_tavily_search(state: TavilySearchState) -> dict[str, object]:
    client = _require_search_client()
    results = await client.search(state["query"], max_results=state["max_results"])
    return {
        "results": results,
        "result_count": len(results),
    }


_COMPILED_GRAPH: TavilySearchGraph | None = None


def build_tavily_search_graph() -> TavilySearchGraph:
    """Build a single-node Tavily search graph for local UI validation."""
    graph: StateGraph[TavilySearchState, TavilySearchState, TavilySearchState] = StateGraph(
        TavilySearchState
    )
    graph.add_node("search_web", _run_tavily_search)
    graph.add_edge(START, "search_web")
    graph.add_edge("search_web", END)
    return graph.compile()


def get_tavily_search_graph() -> TavilySearchGraph:
    """Return the memoized Tavily search graph."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_tavily_search_graph()
    return _COMPILED_GRAPH


def reset_tavily_search_graph_cache() -> None:
    """Clear the memoized Tavily search graph (for tests)."""
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def initial_tavily_search_state(query: str, *, max_results: int = 5) -> TavilySearchState:
    """Build the initial graph state for Tavily search."""
    return TavilySearchState(
        query=query,
        max_results=max_results,
        result_count=0,
    )
