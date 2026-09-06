"""Graph state for the content-generation workflow."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from mcp_server.domain.authoring import GraphNodeHit
from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft
from mcp_server.domain.harness_schemas import (
    HarnessLessonDraft,
    HarnessProjectDraft,
    HarnessQuizDraft,
)


class ContentGenerationState(TypedDict):
    """State carried through lesson → quiz + PBL generation."""

    topic: str
    grade_level: str
    graph_scoped: NotRequired[bool]
    tenant_id: NotRequired[str | None]
    course_slug: NotRequired[str | None]
    module_id: NotRequired[str | None]
    lesson_slug: NotRequired[str | None]
    graph_node_id: NotRequired[str | None]
    graph_index: NotRequired[str | None]
    graph_hits: NotRequired[list[GraphNodeHit]]
    lesson: NotRequired[LessonDraft | HarnessLessonDraft]
    quiz: NotRequired[QuizDraft | HarnessQuizDraft]
    pbl: NotRequired[PBLDraft | HarnessProjectDraft]
    harness_lesson: NotRequired[HarnessLessonDraft]
    harness_quiz: NotRequired[HarnessQuizDraft]
    harness_project: NotRequired[HarnessProjectDraft]
    lesson_validation_errors: NotRequired[list[str]]
    quiz_validation_errors: NotRequired[list[str]]
    pbl_validation_errors: NotRequired[list[str]]
    lesson_retry_count: NotRequired[int]
    quiz_retry_count: NotRequired[int]
    pbl_retry_count: NotRequired[int]
    generation_complete: NotRequired[bool]
    # Author pipeline (graph + module + slug): prefer faster models on quiz/project steps.
    fast_authoring: NotRequired[bool]
