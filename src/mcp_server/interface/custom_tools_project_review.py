"""MCP tools for AI project review (E7)."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from mcp_server.application.agent import ainvoke_with_workflow_timeout
from mcp_server.application.agents.project_review.graph import (
    get_project_review_graph,
    initial_project_review_state,
    result_from_state,
)
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.project_review import (
    ProjectReviewContext,
    ProjectReviewResult,
    ProjectReviewStore,
)
from mcp_server.interface.custom_tools import _cached_tool_invoke
from mcp_server.interface.mcp_server import mcp

_repo: ProjectReviewStore | None = None


def register_project_review_tool_repository(repo: ProjectReviewStore) -> None:
    global _repo
    _repo = repo


def _require_repo() -> ProjectReviewStore:
    if _repo is None:
        raise ResourceNotFoundError("Project review repository not initialized")
    return _repo


class CollectProjectReviewContextRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    course_slug: str = Field(min_length=1)
    module_slug: str = Field(min_length=1)
    lesson_slug: str = Field(min_length=1)
    project_slug: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    delivery_limit: int = Field(default=3, ge=1, le=10)


class ProjectReviewRequest(CollectProjectReviewContextRequest):
    persist: bool = True


@mcp.tool
async def collect_project_review_context(
    tenant_id: str,
    course_slug: str,
    module_slug: str,
    lesson_slug: str,
    project_slug: str,
    user_id: str,
    delivery_limit: int = 3,
) -> ProjectReviewContext:
    """Collect README, starter files, and last N deliveries for project grading."""
    request = CollectProjectReviewContextRequest(
        tenant_id=tenant_id,
        course_slug=course_slug,
        module_slug=module_slug,
        lesson_slug=lesson_slug,
        project_slug=project_slug,
        user_id=user_id,
        delivery_limit=delivery_limit,
    )
    args = request.model_dump()

    async def _run() -> ProjectReviewContext:
        return await asyncio.to_thread(_require_repo().collect_context, **args)

    return await _cached_tool_invoke(
        "collect_project_review_context",
        args,
        _run,
    )


@mcp.tool
async def project_review(
    tenant_id: str,
    course_slug: str,
    module_slug: str,
    lesson_slug: str,
    project_slug: str,
    user_id: str,
    delivery_limit: int = 3,
    persist: bool = True,
) -> ProjectReviewResult:
    """Grade a learner project delivery (0–100) and optionally persist via EF7."""
    request = ProjectReviewRequest(
        tenant_id=tenant_id,
        course_slug=course_slug,
        module_slug=module_slug,
        lesson_slug=lesson_slug,
        project_slug=project_slug,
        user_id=user_id,
        delivery_limit=delivery_limit,
        persist=persist,
    )
    args = request.model_dump()

    async def _run() -> ProjectReviewResult:
        graph = get_project_review_graph()
        state = initial_project_review_state(**args)
        result_state = await ainvoke_with_workflow_timeout(graph, state)
        return result_from_state(result_state)

    return await _cached_tool_invoke(
        "project_review",
        args,
        _run,
    )
