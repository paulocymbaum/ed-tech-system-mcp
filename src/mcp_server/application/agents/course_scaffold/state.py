"""Graph state for structure-only course scaffold generation."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from mcp_server.domain.course_scaffold import ScaffoldProposal


class CourseScaffoldState(TypedDict):
    """State carried through generate → validate."""

    tenant_id: str
    prompt: str
    title: NotRequired[str | None]
    locale: NotRequired[str | None]
    slug: NotRequired[str | None]
    course_slug: NotRequired[str | None]
    proposal: NotRequired[ScaffoldProposal | None]
    validation_errors: NotRequired[list[str]]
    generate_retry_count: NotRequired[int]
    generation_complete: NotRequired[bool]
