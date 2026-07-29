"""State for the research-article LangGraph workflow."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

from mcp_server.domain.schemas import VideoResult


class ToolCallRecord(TypedDict, total=False):
    """One async tool invocation recorded by the orchestrator."""

    tool: str
    status: Literal["ok", "failed"]
    result_count: int
    error: str


class ResearchArticleState(TypedDict):
    """State carried through research → merge → journalistic writing."""

    query: str
    max_web_results: int
    max_video_results: int
    research_brief: NotRequired[str]
    web_results: NotRequired[list[str]]
    videos: NotRequired[list[VideoResult]]
    tavily_tool_call: NotRequired[ToolCallRecord]
    youtube_tool_call: NotRequired[ToolCallRecord]
    tool_calls: NotRequired[list[ToolCallRecord]]
    merged_context: NotRequired[str]
    article: NotRequired[str]
    generation_complete: bool
