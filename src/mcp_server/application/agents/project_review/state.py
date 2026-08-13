"""Graph state for project-review workflow."""

from __future__ import annotations

from typing import Any, TypedDict

from mcp_server.domain.project_review import ProjectReviewContext, ProjectReviewResult


class ProjectReviewState(TypedDict, total=False):
    tenant_id: str
    course_slug: str
    module_slug: str
    lesson_slug: str
    project_slug: str
    user_id: str
    delivery_limit: int
    persist: bool
    context: ProjectReviewContext | None
    score: int | None
    comment: str | None
    validation_errors: list[str]
    grade_retry_count: int
    result: ProjectReviewResult | None
    model_id: str | None
    error: str | None
    llm_io: list[dict[str, Any]]
