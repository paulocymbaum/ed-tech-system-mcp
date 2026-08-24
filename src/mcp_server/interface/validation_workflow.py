"""Workflow and LangGraph validation schemas (Docker / workflow-api only)."""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from mcp_server.application.agents.content_generation.state import ContentGenerationState
from mcp_server.application.agents.rag_retrieval.state import RagRetrievalState
from mcp_server.application.agents.rag_validation.state import RagValidationState
from mcp_server.application.agents.research_article.state import ResearchArticleState
from mcp_server.application.agents.tavily_search.graph import TavilySearchState
from mcp_server.application.agents.youtube_search.graph import YouTubeSearchState
from mcp_server.application.workflow_trace import WorkflowTraceStep
from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft
from mcp_server.domain.input_safety import require_safe_user_text
from mcp_server.domain.schemas import ChunkHit, VideoResult


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


class ContentGenerationRunRequest(BaseModel):
    """Validated input for lesson → quiz + PBL workflow execution."""

    topic: str = Field(min_length=1)
    grade_level: str = Field(default="6th grade", min_length=1)
    tenant_id: str | None = Field(default=None, min_length=36, max_length=36)
    course_slug: str | None = Field(default=None, min_length=1)
    module_id: str | None = Field(default=None, min_length=36, max_length=36)
    lesson_slug: str | None = Field(default=None, min_length=1)
    # Graph leaves may be UUIDs or stable path-like ids such as
    # `lesson:javascript:07-module:07.5-topic`; do not force UUID length here.
    graph_node_id: str | None = Field(default=None, min_length=1)
    graph_query: str | None = Field(default=None, min_length=1)
    graph_hits: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator(
        "topic",
        "grade_level",
        "course_slug",
        "lesson_slug",
        "graph_query",
    )
    @classmethod
    def validate_user_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_safe_user_text(value, field="text")


class ContentGenerationRunResponse(BaseModel):
    """Validated output for lesson → quiz + PBL workflow execution."""

    topic: str
    grade_level: str
    graph_scoped: bool = False
    tenant_id: str | None = None
    course_slug: str | None = None
    graph_node_id: str | None = None
    graph_hits: list[dict[str, Any]] = Field(default_factory=list)
    generation_complete: bool
    lesson_retry_count: int = Field(ge=0)
    quiz_retry_count: int = Field(ge=0)
    pbl_retry_count: int = Field(ge=0)
    lesson: LessonDraft | dict[str, Any] | None = None
    quiz: QuizDraft | dict[str, Any] | None = None
    pbl: PBLDraft | dict[str, Any] | None = None
    harness_lesson: dict[str, Any] | None = None
    harness_quiz: dict[str, Any] | None = None
    harness_project: dict[str, Any] | None = None
    lesson_validation_errors: list[str] = Field(default_factory=list)
    quiz_validation_errors: list[str] = Field(default_factory=list)
    pbl_validation_errors: list[str] = Field(default_factory=list)
    trace: list[WorkflowTraceStepView] = Field(default_factory=list)


class RagRetrievalRunRequest(BaseModel):
    """Validated input for RAG retrieval workflow execution."""

    query: str = Field(min_length=1)
    retrieval_mode: Literal["vector", "hybrid"] = "hybrid"
    retrieve_limit: int = Field(default=20, ge=1, le=100)
    rerank_top_n: int = Field(default=6, ge=1, le=50)
    rerank_enabled: bool = False
    tenant_id: str | None = Field(default=None, min_length=36, max_length=36)
    course_id: str | None = None
    tags: list[str] | None = None
    language: str | None = Field(default=None, min_length=2, max_length=10)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return require_safe_user_text(value, field="query")


class RagEvaluationContextView(BaseModel):
    """Run configuration affecting how retrieval metrics should be interpreted."""

    retrieval_mode: Literal["vector", "hybrid"]
    retrieve_limit: int = Field(ge=1)
    rerank_enabled: bool
    rerank_top_n: int = Field(ge=1)
    effective_k: int = Field(ge=0)
    score_kind: Literal["cosine", "rrf", "reranker"]
    chunk_size: int | None = Field(default=None, ge=1)
    chunk_overlap: int | None = Field(default=None, ge=0)
    indexed_chunk_count: int | None = Field(default=None, ge=0)
    hybrid_fts_active: bool = False
    rerank_applied: bool = False


class RagRetrievalRunResponse(BaseModel):
    """Validated output for RAG retrieval workflow execution."""

    query: str
    retrieval_mode: Literal["vector", "hybrid"]
    retrieval_complete: bool
    chunk_count: int = Field(ge=0)
    chunks: list[ChunkHit] = Field(default_factory=list)
    merged_context: str = ""
    rag_evaluation_context: RagEvaluationContextView | None = None
    trace: list[WorkflowTraceStepView] = Field(default_factory=list)


class RagValidationRunRequest(BaseModel):
    """Validated input for RAG validation workflow execution."""

    query: str | None = None
    fixture_path: str | None = None
    document_text: str | None = None
    document_title: str | None = None
    expected_phrases: list[str] | None = None
    retrieval_mode: Literal["vector", "hybrid"] = "vector"
    retrieve_limit: int = Field(default=10, ge=1, le=100)
    rerank_top_n: int = Field(default=6, ge=1, le=50)
    rerank_enabled: bool = False
    course_id: str | None = None
    tags: list[str] | None = None
    language: str | None = Field(default="en", min_length=2, max_length=10)

    @field_validator("query", "document_text", "document_title")
    @classmethod
    def validate_optional_user_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return require_safe_user_text(value, field="text")


class RagValidationDocumentDefaults(BaseModel):
    """Bundled document defaults for the local UI editor."""

    document_title: str
    document_text: str
    query: str
    expected_phrases: list[str]
    suggested_hyperparameters: dict[str, str | int | bool] | None = None


class RagValidationRunResponse(BaseModel):
    """Validated output for RAG validation workflow execution."""

    query: str
    retrieval_mode: Literal["vector", "hybrid"]
    retrieval_complete: bool
    index_complete: bool
    indexed_chunk_count: int = Field(ge=0)
    document_title: str = ""
    document_source: str = ""
    validation_passed: bool
    validation_errors: list[str] = Field(default_factory=list)
    expected_phrases: list[str] = Field(default_factory=list)
    matched_phrases: list[str] = Field(default_factory=list)
    missing_phrases: list[str] = Field(default_factory=list)
    rag_benchmarks: dict[str, float | int] = Field(default_factory=dict)
    rag_evaluation_context: RagEvaluationContextView | None = None
    chunk_count: int = Field(ge=0)
    chunks: list[ChunkHit] = Field(default_factory=list)
    merged_context: str = ""
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


def _coerce_content_field(value: Any) -> LessonDraft | QuizDraft | PBLDraft | dict[str, Any] | None:
    """Map graph state artifacts into ContentGenerationRunResponse field types.

    Graph-scoped runs store ``Harness*Draft`` on ``lesson``/``quiz``/``pbl``. Those are
    not ``LessonDraft``/``QuizDraft``/``PBLDraft``, so dump them to ``dict`` (accepted
    by the response union) instead of failing Pydantic validation.
    """
    if value is None:
        return None
    if isinstance(value, (LessonDraft, QuizDraft, PBLDraft)):
        return value
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dump = value.model_dump
        # Prefer aliases for harness quiz (correctOptionId) when available.
        try:
            return dump(by_alias=True)  # type: ignore[misc]
        except TypeError:
            return dump()
    return None


def _dump_model(value: Any, *, by_alias: bool = False) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        if by_alias:
            try:
                return value.model_dump(by_alias=True)
            except TypeError:
                return value.model_dump()
        return value.model_dump()
    return None


def content_generation_state_to_run_response(
    state: ContentGenerationState,
    *,
    trace: list[WorkflowTraceStep] | None = None,
) -> ContentGenerationRunResponse:
    """Map a content-generation graph state to the local UI workflow response."""
    harness_lesson = state.get("harness_lesson")
    harness_quiz = state.get("harness_quiz")
    harness_project = state.get("harness_project")
    graph_hits_raw = state.get("graph_hits") or []
    graph_hits = [
        hit.model_dump() if hasattr(hit, "model_dump") else dict(hit)
        for hit in graph_hits_raw
        if hit is not None
    ]
    return ContentGenerationRunResponse(
        topic=state["topic"],
        grade_level=state["grade_level"],
        graph_scoped=bool(state.get("graph_scoped")),
        tenant_id=state.get("tenant_id"),
        course_slug=state.get("course_slug"),
        graph_node_id=state.get("graph_node_id"),
        graph_hits=graph_hits,
        generation_complete=state.get("generation_complete", False),
        lesson_retry_count=state.get("lesson_retry_count", 0),
        quiz_retry_count=state.get("quiz_retry_count", 0),
        pbl_retry_count=state.get("pbl_retry_count", 0),
        lesson=_coerce_content_field(state.get("lesson")),
        quiz=_coerce_content_field(state.get("quiz")),
        pbl=_coerce_content_field(state.get("pbl")),
        harness_lesson=_dump_model(harness_lesson, by_alias=True),
        harness_quiz=_dump_model(harness_quiz, by_alias=True),
        harness_project=_dump_model(harness_project, by_alias=True),
        lesson_validation_errors=state.get("lesson_validation_errors", []),
        quiz_validation_errors=state.get("quiz_validation_errors", []),
        pbl_validation_errors=state.get("pbl_validation_errors", []),
        trace=trace_steps_to_views(trace or []),
    )


def _rag_evaluation_context_from_state(
    state: RagRetrievalState | RagValidationState,
) -> RagEvaluationContextView | None:
    raw = state.get("rag_evaluation_context")
    if not raw:
        return None
    return RagEvaluationContextView.model_validate(raw)


def rag_retrieval_state_to_run_response(
    state: RagRetrievalState,
    *,
    trace: list[WorkflowTraceStep] | None = None,
) -> RagRetrievalRunResponse:
    """Map a RAG retrieval graph state to the local UI workflow response."""
    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks", [])
    return RagRetrievalRunResponse(
        query=state["query"],
        retrieval_mode=state["retrieval_mode"],
        retrieval_complete=state.get("retrieval_complete", False),
        chunk_count=len(chunks),
        chunks=chunks,
        merged_context=state.get("merged_context", ""),
        rag_evaluation_context=_rag_evaluation_context_from_state(state),
        trace=trace_steps_to_views(trace or []),
    )


def rag_validation_state_to_run_response(
    state: RagValidationState,
    *,
    trace: list[WorkflowTraceStep] | None = None,
) -> RagValidationRunResponse:
    """Map a RAG validation graph state to the local UI workflow response."""
    from mcp_server.application.agents.rag_validation.fixture import load_expected_phrases

    chunks = state.get("reranked_chunks") or state.get("retrieved_chunks", [])
    return RagValidationRunResponse(
        query=state["query"],
        retrieval_mode=state["retrieval_mode"],
        retrieval_complete=state.get("retrieval_complete", False),
        index_complete=state.get("index_complete", False),
        indexed_chunk_count=state.get("indexed_chunk_count", 0),
        document_title=state.get("document_title", ""),
        document_source=state.get("document_source", ""),
        validation_passed=state.get("validation_passed", False),
        validation_errors=list(state.get("validation_errors", [])),
        expected_phrases=load_expected_phrases(state.get("expected_phrases")),
        matched_phrases=list(state.get("matched_phrases", [])),
        missing_phrases=list(state.get("missing_phrases", [])),
        rag_benchmarks=dict(state.get("rag_benchmarks", {})),
        rag_evaluation_context=_rag_evaluation_context_from_state(state),
        chunk_count=len(chunks),
        chunks=chunks,
        merged_context=state.get("merged_context", ""),
        trace=trace_steps_to_views(trace or []),
    )
