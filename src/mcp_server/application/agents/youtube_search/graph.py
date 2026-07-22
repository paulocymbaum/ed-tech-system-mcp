"""LangGraph workflow for YouTube video search."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from mcp_server.application.integration_runtime import get_video_client
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.schemas import VideoResult

YouTubeSearchGraph = CompiledStateGraph[
    "YouTubeSearchState", "YouTubeSearchState", "YouTubeSearchState"
]


class YouTubeSearchState(TypedDict):
    """State carried through the YouTube search graph."""

    query: str
    max_results: int
    language: str
    safe_search: bool
    videos: NotRequired[list[VideoResult]]
    video_count: int


def _require_video_client():
    client = get_video_client()
    if client is None:
        raise ResourceNotFoundError("Video search client has not been initialized")
    return client


async def _run_youtube_search(state: YouTubeSearchState) -> dict[str, object]:
    client = _require_video_client()
    videos = await client.search_videos(
        state["query"],
        max_results=state["max_results"],
        language=state["language"],
        safe_search=state["safe_search"],
    )
    return {
        "videos": videos,
        "video_count": len(videos),
    }


_COMPILED_GRAPH: YouTubeSearchGraph | None = None


def build_youtube_search_graph() -> YouTubeSearchGraph:
    """Build a single-node YouTube search graph for local UI validation."""
    graph: StateGraph[YouTubeSearchState, YouTubeSearchState, YouTubeSearchState] = StateGraph(
        YouTubeSearchState
    )
    graph.add_node("search_videos", _run_youtube_search)
    graph.add_edge(START, "search_videos")
    graph.add_edge("search_videos", END)
    return graph.compile()


def get_youtube_search_graph() -> YouTubeSearchGraph:
    """Return the memoized YouTube search graph."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_youtube_search_graph()
    return _COMPILED_GRAPH


def reset_youtube_search_graph_cache() -> None:
    """Clear the memoized YouTube search graph (for tests)."""
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def initial_youtube_search_state(
    query: str,
    *,
    max_results: int = 5,
    language: str = "en",
    safe_search: bool = True,
) -> YouTubeSearchState:
    """Build the initial graph state for YouTube search."""
    return YouTubeSearchState(
        query=query,
        max_results=max_results,
        language=language,
        safe_search=safe_search,
        video_count=0,
    )
