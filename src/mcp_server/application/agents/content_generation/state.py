"""Graph state for the content-generation workflow."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft


class ContentGenerationState(TypedDict):
    """State carried through lesson → quiz + PBL generation."""

    topic: str
    grade_level: str
    lesson: NotRequired[LessonDraft]
    quiz: NotRequired[QuizDraft]
    pbl: NotRequired[PBLDraft]
    lesson_validation_errors: NotRequired[list[str]]
    quiz_validation_errors: NotRequired[list[str]]
    pbl_validation_errors: NotRequired[list[str]]
    lesson_retry_count: NotRequired[int]
    quiz_retry_count: NotRequired[int]
    pbl_retry_count: NotRequired[int]
    generation_complete: NotRequired[bool]
