"""MCP tools for graph-scoped lesson authoring (E6)."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from mcp_server.application.author_job_progress import report_ai_generation_job
from mcp_server.application.author_lesson_pipeline import (
    AuthorLessonPipelineResponse,
    run_author_lesson_pipeline,
)
from mcp_server.application.authoring_service import (
    AuthoringService,
    validate_lesson_dict,
    validate_project_dict,
    validate_quiz_dict,
)
from mcp_server.application.course_scaffold_runner import invoke_course_scaffold
from mcp_server.application.mock_test_authoring import build_mock_test_structure
from mcp_server.domain.ai_generation_job import AiGenerationJobProgressPort
from mcp_server.domain.authoring import (
    AuthoringBackendFactoryPort,
    GraphNodeHit,
    GraphSearchPort,
    MockTestStructureResult,
    SaveLessonResult,
)
from mcp_server.domain.content_validators import (
    validate_mock_test_bundle,
    validate_test_boilerplate,
)
from mcp_server.domain.course_scaffold import (
    ScaffoldEdge,
    ScaffoldNode,
    slugify_course_title,
)
from mcp_server.domain.exceptions import DomainValidationError, ResourceNotFoundError
from mcp_server.interface.custom_tools import _cached_tool_invoke
from mcp_server.interface.mcp_server import mcp

_graph_search: GraphSearchPort | None = None
_backend_factory: AuthoringBackendFactoryPort | None = None
_job_progress: AiGenerationJobProgressPort | None = None


def register_authoring_tools(
    *,
    graph_search: GraphSearchPort,
    backend_factory: AuthoringBackendFactoryPort,
    job_progress: AiGenerationJobProgressPort | None = None,
) -> None:
    """Wire authoring dependencies from composition root."""
    global _graph_search, _backend_factory, _job_progress
    _graph_search = graph_search
    _backend_factory = backend_factory
    _job_progress = job_progress


def _require_graph_search() -> GraphSearchPort:
    if _graph_search is None:
        raise ResourceNotFoundError("Graph search repository has not been initialized")
    return _graph_search


def _require_backend_factory() -> AuthoringBackendFactoryPort:
    if _backend_factory is None:
        raise ResourceNotFoundError("Authoring backend factory has not been initialized")
    return _backend_factory


class ValidationToolResponse(BaseModel):
    ok: bool
    findings: list[str] = Field(default_factory=list)


class GenerateCourseScaffoldResponse(BaseModel):
    """Structure-only proposal. BFF extractScaffoldProposal reads nodes/edges."""

    nodes: list[ScaffoldNode] = Field(default_factory=list)
    edges: list[ScaffoldEdge] = Field(default_factory=list)


@mcp.tool
async def validate_quiz(quiz: dict[str, Any]) -> ValidationToolResponse:
    """Validate quiz JSON against EdHarness rules (option slugs + correctOptionId)."""
    findings = validate_quiz_dict(quiz)
    return ValidationToolResponse(
        ok=not any(f.startswith("error:") for f in findings), findings=findings
    )


@mcp.tool
async def validate_project(project: dict[str, Any]) -> ValidationToolResponse:
    """Validate PBL project draft (README sections, tests.json cases)."""
    findings = validate_project_dict(project)
    return ValidationToolResponse(
        ok=not any(f.startswith("error:") for f in findings), findings=findings
    )


@mcp.tool(name="validate_test_boilerplate")
async def validate_test_boilerplate_tool(
    boilerplate: dict[str, Any],
) -> ValidationToolResponse:
    """Validate harness body has LEARNER_CODE and runner_kind is known (E16.15)."""
    report = validate_test_boilerplate(boilerplate)
    findings = [f"{f.level}: {f.message}" for f in report.findings]
    return ValidationToolResponse(ok=report.ok, findings=findings)


@mcp.tool
async def validate_lesson(
    lesson: dict[str, Any],
    quiz: dict[str, Any] | None = None,
) -> ValidationToolResponse:
    """Validate lesson README + meta (+ optional quiz)."""
    findings = validate_lesson_dict(lesson, quiz=quiz)
    return ValidationToolResponse(
        ok=not any(f.startswith("error:") for f in findings), findings=findings
    )


@mcp.tool
async def save_to_backend(
    manager_jwt: str,
    module_id: str,
    lesson_slug: str,
    lesson: dict[str, Any],
    quiz: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
    publish: bool = False,
) -> SaveLessonResult:
    """Persist lesson bundle via public RPCs. Requires manager+ user JWT (not service_role)."""
    factory = _require_backend_factory()
    backend = factory.for_jwt(manager_jwt)
    service = AuthoringService(backend)
    args = {
        "module_id": module_id,
        "lesson_slug": lesson_slug,
        "publish": publish,
    }

    async def _run() -> SaveLessonResult:
        return await service.save_lesson_bundle(
            module_id=module_id,
            lesson_slug=lesson_slug,
            lesson=lesson,
            quiz=quiz,
            project=project,
            publish=publish,
        )

    return await _cached_tool_invoke("save_to_backend", args, _run)


@mcp.tool
async def generate_course_scaffold(
    manager_jwt: str,
    tenant_id: str,
    prompt: str,
    title: str | None = None,
    locale: str | None = None,
    slug: str | None = None,
    course_slug: str | None = None,
    job_id: str | None = None,
) -> GenerateCourseScaffoldResponse:
    """Generate a structure-only course graph proposal. Does not apply the live graph."""
    if not manager_jwt.strip():
        raise DomainValidationError("manager_jwt is required")
    if not tenant_id.strip():
        raise DomainValidationError("tenant_id is required")
    if not prompt.strip():
        raise DomainValidationError("prompt is required")
    resolved_slug = (course_slug or slug or "").strip() or None
    if resolved_slug is None:
        if not (title or "").strip():
            raise DomainValidationError("slug, course_slug, or title is required")
        resolved_slug = slugify_course_title(title or "")
    progress = _job_progress if job_id else None
    try:
        proposal = await invoke_course_scaffold(
            tenant_id=tenant_id.strip(),
            prompt=prompt.strip(),
            title=(title.strip() if title else None),
            locale=(locale.strip() if locale else None),
            slug=(slug.strip() if slug else None),
            course_slug=(course_slug.strip() if course_slug else None) or resolved_slug,
            job_id=job_id,
            job_progress=progress,
        )
    except Exception:
        if job_id:
            await report_ai_generation_job(
                progress,
                job_id=job_id,
                status="failed",
                error="Course scaffold generation failed",
            )
        raise
    return GenerateCourseScaffoldResponse(nodes=proposal.nodes, edges=proposal.edges)


@mcp.tool
async def author_lesson_pipeline(
    manager_jwt: str,
    tenant_id: str,
    course_slug: str,
    module_id: str,
    topic: str,
    lesson_slug: str,
    grade_level: str = "6th grade",
    graph_node_id: str | None = None,
    graph_query: str | None = None,
    graph_index: str | None = None,
    publish: bool = False,
    job_id: str | None = None,
) -> AuthorLessonPipelineResponse:
    """Orchestrate search → generate → validate → save → publish (graph-scoped)."""
    return await run_author_lesson_pipeline(
        manager_jwt=manager_jwt,
        tenant_id=tenant_id,
        course_slug=course_slug,
        module_id=module_id,
        topic=topic,
        lesson_slug=lesson_slug,
        grade_level=grade_level,
        graph_node_id=graph_node_id,
        graph_query=graph_query,
        graph_index=graph_index,
        publish=publish,
        job_id=job_id,
        graph_search=_require_graph_search(),
        backend_factory=_require_backend_factory(),
        job_progress=_job_progress,
    )


class SearchGraphNodesResponse(BaseModel):
    query: str
    tenant_id: str
    course_slug: str | None = None
    results: list[GraphNodeHit]


class ValidateMockTestResponse(BaseModel):
    ok: bool
    messages: list[str] = Field(default_factory=list)


@mcp.tool
async def search_graph_nodes(
    tenant_id: str,
    query: str,
    course_slug: str | None = None,
    min_similarity: float = 0.1,
    limit: int = 5,
) -> SearchGraphNodesResponse:
    """Search curriculum topic graph nodes (EF9 / RPC ``search_graph_nodes``)."""
    args = {
        "tenant_id": tenant_id,
        "query": query,
        "course_slug": course_slug,
        "min_similarity": min_similarity,
        "limit": limit,
    }

    async def _run() -> SearchGraphNodesResponse:
        hits = await asyncio.to_thread(_require_graph_search().search_graph_nodes, **args)
        return SearchGraphNodesResponse(
            query=query.strip(),
            tenant_id=tenant_id,
            course_slug=course_slug,
            results=hits,
        )

    return await _cached_tool_invoke("search_graph_nodes", args, _run)


@mcp.tool
async def generate_mock_test_structure(
    study_module_slug: str,
    mock_module_slug: str | None = None,
    duration_minutes: int = 90,
    passing_score_percent: int = 70,
    instructions_lesson_slug: str | None = None,
    quiz_lesson_slug: str | None = None,
    coding_lesson_slug: str | None = None,
) -> MockTestStructureResult:
    """Build a validated three-section mock test payload for EF2 ``mock_tests``."""
    args = {
        "study_module_slug": study_module_slug,
        "mock_module_slug": mock_module_slug,
        "duration_minutes": duration_minutes,
        "passing_score_percent": passing_score_percent,
        "instructions_lesson_slug": instructions_lesson_slug,
        "quiz_lesson_slug": quiz_lesson_slug,
        "coding_lesson_slug": coding_lesson_slug,
    }

    async def _run() -> MockTestStructureResult:
        return build_mock_test_structure(**args)

    return await _cached_tool_invoke("generate_mock_test_structure", args, _run)


@mcp.tool
async def validate_mock_test(mock_test: dict[str, Any]) -> ValidateMockTestResponse:
    """Validate an EF2 ``mock_tests[]`` entry (instructions → quiz → coding)."""
    args = {"mock_test": mock_test}

    async def _run() -> ValidateMockTestResponse:
        report = validate_mock_test_bundle(mock_test)
        return ValidateMockTestResponse(
            ok=report.ok,
            messages=[f"[{f.level}] {f.message}" for f in report.findings],
        )

    return await _cached_tool_invoke("validate_mock_test", args, _run)
