"""Graph state for socratic tutor workflow."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from mcp_server.domain.socratic import (
    LocaleCode,
    SocraticGrounding,
    SocraticMessage,
    SocraticReply,
)


class SocraticTutorState(TypedDict):
    tenant_id: str
    course_slug: str
    module_slug: NotRequired[str | None]
    lesson_slug: NotRequired[str | None]
    project_slug: NotRequired[str | None]
    message: str
    history: list[SocraticMessage]
    hint_level: int
    locale: LocaleCode
    want_full_solution: bool
    grounding: NotRequired[SocraticGrounding | None]
    reply: NotRequired[str | None]
    validation_errors: NotRequired[list[str]]
    reply_retry_count: NotRequired[int]
    result: NotRequired[SocraticReply | None]
    error: NotRequired[str | None]
    model_id: NotRequired[str | None]
    llm_io: NotRequired[list[object]]
    session_id: NotRequired[str | None]
