"""MCP tools for Socratic tutor (E8)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from mcp_server.application.agents.socratic.graph import (
    get_socratic_tutor_graph,
    initial_socratic_tutor_state,
    result_from_state,
)
from mcp_server.application.agent import workflow_timeout_seconds
from mcp_server.application.workflow_trace import invoke_graph_with_trace
from mcp_server.domain.socratic import SocraticMessage, SocraticReply, normalize_locale
from mcp_server.interface.custom_tools import _cached_tool_invoke
from mcp_server.interface.mcp_server import mcp


class SocraticHistoryItem(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class SocraticTutorRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    course_slug: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=4000)
    module_slug: str | None = None
    lesson_slug: str | None = None
    project_slug: str | None = None
    history: list[SocraticHistoryItem] = Field(default_factory=list)
    hint_level: int = Field(default=1, ge=1, le=5)
    locale: str = "en"
    want_full_solution: bool = False


@mcp.tool
async def socratic_tutor(
    tenant_id: str,
    course_slug: str,
    message: str,
    module_slug: str | None = None,
    lesson_slug: str | None = None,
    project_slug: str | None = None,
    history: list[dict[str, str]] | None = None,
    hint_level: int = 1,
    locale: str = "en",
    want_full_solution: bool = False,
) -> SocraticReply:
    """Socratic tutoring turn — hints and questions; never grades."""
    hist_items = [
        SocraticHistoryItem.model_validate(item) for item in (history or [])
    ]
    request = SocraticTutorRequest(
        tenant_id=tenant_id,
        course_slug=course_slug,
        message=message,
        module_slug=module_slug,
        lesson_slug=lesson_slug,
        project_slug=project_slug,
        history=hist_items,
        hint_level=hint_level,
        locale=locale,
        want_full_solution=want_full_solution,
    )
    args = request.model_dump()

    async def _run() -> SocraticReply:
        graph = get_socratic_tutor_graph()
        state = initial_socratic_tutor_state(
            tenant_id=request.tenant_id,
            course_slug=request.course_slug,
            message=request.message,
            module_slug=request.module_slug,
            lesson_slug=request.lesson_slug,
            project_slug=request.project_slug,
            history=[
                SocraticMessage(role=h.role, content=h.content)  # type: ignore[arg-type]
                for h in request.history
            ],
            hint_level=request.hint_level,
            locale=normalize_locale(request.locale),
            want_full_solution=request.want_full_solution,
        )
        result_state, _trace = await invoke_graph_with_trace(
            graph,
            state,
            timeout_seconds=workflow_timeout_seconds(),
        )
        return result_from_state(result_state)

    return await _cached_tool_invoke("socratic_tutor", args, _run)
