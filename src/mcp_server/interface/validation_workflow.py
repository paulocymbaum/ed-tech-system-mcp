"""Workflow and LangGraph validation schemas (Docker / workflow-api only)."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from mcp_server.application.agents.research_article.state import ResearchArticleState
from mcp_server.application.agents.tavily_search.graph import TavilySearchState
from mcp_server.application.agents.youtube_search.graph import YouTubeSearchState
from mcp_server.application.content_generation_dtos import (
    WorkflowTraceStepView,
    trace_steps_to_views,
)
from mcp_server.application.workflow_trace import WorkflowTraceStep
from mcp_server.domain.input_safety import require_safe_user_text
from mcp_server.domain.schemas import VideoResult


class TavilySearchRunRequest(BaseModel):
    """Validated input for Tavily search workflow execution."""

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=25)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return require_safe_user_text(value, field="query")


class TavilySearchRunResponse(BaseModel):
    """Validated output for Tavily search workflow execution."""

    query: str
    result_count: int = Field(ge=0)
    results: list[str]
    trace: list[WorkflowTraceStepView] = Field(default_factory=list)


class YouTubeSearchRunRequest(BaseModel):
    """Validated input for YouTube search workflow execution."""

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=25)
    language: str = Field(default="en", min_length=2, max_length=10)
    safe_search: bool = True

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return require_safe_user_text(value, field="query")


class YouTubeSearchRunResponse(BaseModel):
    """Validated output for YouTube search workflow execution."""

    query: str
    video_count: int = Field(ge=0)
    videos: list[VideoResult]
    trace: list[WorkflowTraceStepView] = Field(default_factory=list)


class ResearchArticleRunRequest(BaseModel):
    """Validated input for research-article workflow execution."""

    query: str = Field(min_length=1)
    max_web_results: int = Field(default=5, ge=1, le=25)
    max_video_results: int = Field(default=3, ge=1, le=25)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return require_safe_user_text(value, field="query")


class ResearchArticleRunResponse(BaseModel):
    """Validated output for research-article workflow execution."""

    query: str
    generation_complete: bool
    research_brief: str = ""
    web_result_count: int = Field(ge=0)
    video_count: int = Field(ge=0)
    web_results: list[str] = Field(default_factory=list)
    videos: list[VideoResult] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    merged_context: str = ""
    article: str = ""
    trace: list[WorkflowTraceStepView] = Field(default_factory=list)


def tavily_search_state_to_run_response(
    state: TavilySearchState,
    *,
    trace: list[WorkflowTraceStep] | None = None,
) -> TavilySearchRunResponse:
    """Map a Tavily search graph state to the local UI workflow response."""
    return TavilySearchRunResponse(
        query=state["query"],
        result_count=state.get("result_count", 0),
        results=state.get("results", []),
        trace=trace_steps_to_views(trace or []),
    )


def youtube_search_state_to_run_response(
    state: YouTubeSearchState,
    *,
    trace: list[WorkflowTraceStep] | None = None,
) -> YouTubeSearchRunResponse:
    """Map a YouTube search graph state to the local UI workflow response."""
    return YouTubeSearchRunResponse(
        query=state["query"],
        video_count=state.get("video_count", 0),
        videos=state.get("videos", []),
        trace=trace_steps_to_views(trace or []),
    )


def research_article_state_to_run_response(
    state: ResearchArticleState,
    *,
    trace: list[WorkflowTraceStep] | None = None,
) -> ResearchArticleRunResponse:
    """Map a research-article graph state to the local UI workflow response."""
    web_results = state.get("web_results", [])
    videos = state.get("videos", [])
    return ResearchArticleRunResponse(
        query=state["query"],
        generation_complete=state.get("generation_complete", False),
        research_brief=state.get("research_brief", ""),
        web_result_count=len(web_results),
        video_count=len(videos),
        web_results=web_results,
        videos=videos,
        tool_calls=[dict(tool_call) for tool_call in state.get("tool_calls", [])],
        merged_context=state.get("merged_context", ""),
        article=state.get("article", ""),
        trace=trace_steps_to_views(trace or []),
    )
