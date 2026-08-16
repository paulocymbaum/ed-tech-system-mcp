"""MCP tools for graph-scoped lesson authoring (E6)."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from mcp_server.application.authoring_service import (
    AuthoringService,
    validate_lesson_dict,
    validate_project_dict,
    validate_quiz_dict,
)
from mcp_server.domain.content_validators import validate_mock_test_bundle, validate_test_boilerplate
from mcp_server.application.content_generation_runner import invoke_content_generation
from mcp_server.application.mock_test_authoring import build_mock_test_structure
from mcp_server.domain.authoring import (
    AuthoringBackendFactoryPort,
    GraphNodeHit,
    GraphSearchPort,
    MockTestStructureResult,
    SaveLessonResult,
)
from mcp_server.domain.exceptions import DomainValidationError, ResourceNotFoundError
from mcp_server.interface.custom_tools import _cached_tool_invoke
from mcp_server.interface.mcp_server import mcp
from mcp_server.interface.validation_workflow import (
    ContentGenerationRunRequest,
    ContentGenerationRunResponse,
)

_graph_search: GraphSearchPort | None = None
_backend_factory: AuthoringBackendFactoryPort | None = None


def register_authoring_tools(
    *,
    graph_search: GraphSearchPort,
    backend_factory: AuthoringBackendFactoryPort,
) -> None:
    """Wire authoring dependencies from composition root."""
    global _graph_search, _backend_factory
    _graph_search = graph_search
    _backend_factory = backend_factory


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


class AuthorLessonPipelineResponse(BaseModel):
    graph_hits: list[dict[str, Any]] = Field(default_factory=list)
    graph_node_id: str | None = None
    generation: ContentGenerationRunResponse
    validation_findings: list[str] = Field(default_factory=list)
    save_result: SaveLessonResult | None = None
    catalog_refresh_note: str = (
        "After publish/save, catalog refresh is enqueued by RPC (EF3 refresh-course-catalog)."
    )


def _resolve_graph_node(
    *,
    tenant_id: str,
    course_slug: str,
    graph_node_id: str | None,
    graph_query: str | None,
    topic: str,
) -> tuple[str | None, list[dict[str, Any]]]:
    search = _require_graph_search()
    query = graph_query or topic
    hits = search.search_graph_nodes(
        tenant_id=tenant_id,
        query=query,
        course_slug=course_slug,
    )
    serialized = [hit.model_dump() for hit in hits]
    if graph_node_id:
        return graph_node_id, serialized
    if hits:
        return hits[0].node_id, serialized
    return None, serialized


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
    publish: bool = False,
) -> AuthorLessonPipelineResponse:
    """Orchestrate search → generate → validate → save → publish (graph-scoped)."""
    resolved_node_id, graph_hits = await asyncio.to_thread(
        _resolve_graph_node,
        tenant_id=tenant_id,
        course_slug=course_slug,
        graph_node_id=graph_node_id,
        graph_query=graph_query,
        topic=topic,
    )
    gen_request = ContentGenerationRunRequest(
        topic=topic,
        grade_level=grade_level,
        tenant_id=tenant_id,
        course_slug=course_slug,
        module_id=module_id,
        lesson_slug=lesson_slug,
        graph_node_id=resolved_node_id,
        graph_query=graph_query,
    )
    generation = await invoke_content_generation(
        gen_request,
        graph_search=_require_graph_search(),
    )

    harness_lesson = generation.harness_lesson
    harness_quiz = generation.harness_quiz
    harness_project = generation.harness_project
    if harness_lesson is None:
        raise DomainValidationError("Graph-scoped generation did not produce harness_lesson")

    findings: list[str] = []
    findings.extend(validate_lesson_dict(harness_lesson, quiz=harness_quiz))
    if harness_quiz:
        findings.extend(validate_quiz_dict(harness_quiz))
    if harness_project:
        findings.extend(
            validate_project_dict(harness_project, strict_readme_sections=False)
        )
    if any(f.startswith("error:") for f in findings):
        return AuthorLessonPipelineResponse(
            graph_hits=graph_hits,
            graph_node_id=resolved_node_id,
            generation=generation,
            validation_findings=findings,
        )

    factory = _require_backend_factory()
    backend = factory.for_jwt(manager_jwt)
    service = AuthoringService(backend)
    save_result = await service.save_lesson_bundle(
        module_id=module_id,
        lesson_slug=lesson_slug,
        lesson=harness_lesson,
        quiz=harness_quiz,
        project=harness_project,
        publish=publish,
    )
    return AuthorLessonPipelineResponse(
        graph_hits=graph_hits,
        graph_node_id=resolved_node_id,
        generation=generation,
        validation_findings=findings,
        save_result=save_result,
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
