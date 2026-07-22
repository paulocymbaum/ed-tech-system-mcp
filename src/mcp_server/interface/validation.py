"""Pydantic validation schemas for MCP tool I/O."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from mcp_server.application.agent import DocumentVideoState
from mcp_server.application.agents.content_generation.state import ContentGenerationState
from mcp_server.application.agents.research_article.state import ResearchArticleState
from mcp_server.application.agents.tavily_search.graph import TavilySearchState
from mcp_server.application.agents.youtube_search.graph import YouTubeSearchState
from mcp_server.application.workflow_trace import WorkflowTraceStep
from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft
from mcp_server.domain.schemas import DocumentHit, VideoResult


class WorkflowTraceStepView(BaseModel):
    """One replayable step from a LangGraph ``stream_mode='updates'`` execution."""

    step: int = Field(ge=1)
    node_id: str
    status: Literal["ok", "failed", "retry"]
    attempt: int = Field(ge=1)
    validation_errors: list[str] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    output_update: dict[str, Any] = Field(default_factory=dict)
    llm_io: dict[str, Any] | None = None


class DocumentSummary(BaseModel):
    """Pruned document payload for MCP JSON-RPC responses."""

    id: str
    title: str
    snippet: str


class DocumentQueryRequest(BaseModel):
    """Validated input for document + video discovery tool calls."""

    query: str = Field(min_length=1)
    document_limit: int = Field(default=10, ge=1, le=50)
    video_limit: int = Field(default=5, ge=1, le=25)


class DocumentQueryResponse(BaseModel):
    """Validated output for document + video discovery tool calls."""

    documents: list[DocumentSummary]
    videos: list[VideoResult]


class VideoSearchRequest(BaseModel):
    """Validated input for video search tool calls."""

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=25)
    language: str = Field(default="en", min_length=2, max_length=10)
    safe_search: bool = True


class VideoSearchResponse(BaseModel):
    """Validated output for video search tool calls."""

    videos: list[VideoResult]


class WorkflowRunRequest(BaseModel):
    """Validated input for LangGraph workflow execution."""

    query: str = Field(min_length=1)
    document_limit: int = Field(default=10, ge=1, le=50)
    video_limit: int = Field(default=5, ge=1, le=25)


class WorkflowRunResponse(BaseModel):
    """Validated output for LangGraph workflow execution."""

    query: str
    search_terms: str
    document_count: int = Field(ge=0)
    video_count: int = Field(ge=0)
    documents: list[DocumentSummary]
    videos: list[VideoResult]
    trace: list[WorkflowTraceStepView] = Field(default_factory=list)


class TavilySearchRunRequest(BaseModel):
    """Validated input for Tavily search workflow execution."""

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=25)


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


class ContentGenerationRunRequest(BaseModel):
    """Validated input for lesson → quiz + PBL workflow execution."""

    topic: str = Field(min_length=1)
    grade_level: str = Field(default="6th grade", min_length=1)


class ContentGenerationRunResponse(BaseModel):
    """Validated output for lesson → quiz + PBL workflow execution."""

    topic: str
    grade_level: str
    generation_complete: bool
    lesson_retry_count: int = Field(ge=0)
    quiz_retry_count: int = Field(ge=0)
    pbl_retry_count: int = Field(ge=0)
    lesson: LessonDraft | None = None
    quiz: QuizDraft | None = None
    pbl: PBLDraft | None = None
    lesson_validation_errors: list[str] = Field(default_factory=list)
    quiz_validation_errors: list[str] = Field(default_factory=list)
    pbl_validation_errors: list[str] = Field(default_factory=list)
    trace: list[WorkflowTraceStepView] = Field(default_factory=list)


def trace_steps_to_views(steps: list[WorkflowTraceStep]) -> list[WorkflowTraceStepView]:
    """Map application trace records to API response DTOs."""
    return [
        WorkflowTraceStepView(
            step=step.step,
            node_id=step.node_id,
            status=step.status,
            attempt=step.attempt,
            validation_errors=list(step.validation_errors),
            retry_counts=dict(step.retry_counts),
            input_snapshot=dict(step.input_snapshot),
            output_update=dict(step.output_update),
            llm_io=step.llm_io,
        )
        for step in steps
    ]


def document_hit_to_summary(hit: DocumentHit, *, snippet_max_len: int = 200) -> DocumentSummary:
    """Map a domain document hit to a pruned MCP response DTO."""
    content = hit.content
    if len(content) <= snippet_max_len:
        snippet = content
    else:
        snippet = f"{content[:snippet_max_len]}..."
    return DocumentSummary(id=hit.id, title=hit.title, snippet=snippet)


def document_hits_to_summaries(
    hits: list[DocumentHit],
    *,
    snippet_max_len: int = 200,
) -> list[DocumentSummary]:
    """Map domain document hits to pruned MCP summaries."""
    return [document_hit_to_summary(hit, snippet_max_len=snippet_max_len) for hit in hits]


def workflow_state_to_run_response(
    state: DocumentVideoState,
    *,
    trace: list[WorkflowTraceStep] | None = None,
) -> WorkflowRunResponse:
    """Map a document-video graph state to the MCP/local UI workflow response."""
    documents = state.get("documents", [])
    videos = state.get("videos", [])
    return WorkflowRunResponse(
        query=state["query"],
        search_terms=state["search_terms"],
        document_count=state["document_count"],
        video_count=state["video_count"],
        documents=document_hits_to_summaries(documents),
        videos=videos,
        trace=trace_steps_to_views(trace or []),
    )


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
        tool_calls=list(state.get("tool_calls", [])),
        merged_context=state.get("merged_context", ""),
        article=state.get("article", ""),
        trace=trace_steps_to_views(trace or []),
    )


def content_generation_state_to_run_response(
    state: ContentGenerationState,
    *,
    trace: list[WorkflowTraceStep] | None = None,
) -> ContentGenerationRunResponse:
    """Map a content-generation graph state to the local UI workflow response."""
    return ContentGenerationRunResponse(
        topic=state["topic"],
        grade_level=state["grade_level"],
        generation_complete=state.get("generation_complete", False),
        lesson_retry_count=state.get("lesson_retry_count", 0),
        quiz_retry_count=state.get("quiz_retry_count", 0),
        pbl_retry_count=state.get("pbl_retry_count", 0),
        lesson=state.get("lesson"),
        quiz=state.get("quiz"),
        pbl=state.get("pbl"),
        lesson_validation_errors=state.get("lesson_validation_errors", []),
        quiz_validation_errors=state.get("quiz_validation_errors", []),
        pbl_validation_errors=state.get("pbl_validation_errors", []),
        trace=trace_steps_to_views(trace or []),
    )
