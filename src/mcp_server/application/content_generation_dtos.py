"""Content-generation run DTOs (application layer)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from mcp_server.application.agents.content_generation.state import ContentGenerationState
from mcp_server.application.workflow_trace import WorkflowTraceStep
from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft
from mcp_server.domain.input_safety import require_safe_user_text


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


class ContentGenerationRunRequest(BaseModel):
    """Validated input for lesson → quiz + PBL workflow execution."""

    topic: str = Field(min_length=1)
    grade_level: str = Field(default="6th grade", min_length=1)
    tenant_id: str | None = Field(default=None, min_length=36, max_length=36)
    course_slug: str | None = Field(default=None, min_length=1)
    module_id: str | None = Field(default=None, min_length=36, max_length=36)
    lesson_slug: str | None = Field(default=None, min_length=1)
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


def _coerce_content_field(value: Any) -> LessonDraft | QuizDraft | PBLDraft | dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, (LessonDraft, QuizDraft, PBLDraft)):
        return value
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dump = value.model_dump
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
    """Map a content-generation graph state to the run response DTO."""
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
