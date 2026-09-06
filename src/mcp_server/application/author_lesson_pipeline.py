"""Graph-scoped author lesson pipeline (search → generate → validate → save)."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from mcp_server.application.author_job_progress import (
    AUTHOR_PIPELINE_FAILED_ERROR,
    load_succeeded_author_save_result,
    report_ai_generation_job,
)
from mcp_server.application.authoring_service import (
    AuthoringService,
    graph_node_id_for_upsert,
    validate_lesson_dict,
    validate_project_dict,
    validate_quiz_dict,
)
from mcp_server.application.content_generation_dtos import (
    ContentGenerationRunRequest,
    ContentGenerationRunResponse,
)
from mcp_server.application.content_generation_runner import invoke_content_generation
from mcp_server.domain.ai_generation_job import AiGenerationJobProgressPort
from mcp_server.domain.authoring import (
    AuthoringBackendFactoryPort,
    GraphNodeHit,
    GraphSearchPort,
    SaveLessonResult,
)
from mcp_server.domain.exceptions import DomainValidationError


class AuthorLessonPipelineResponse(BaseModel):
    graph_hits: list[dict[str, Any]] = Field(default_factory=list)
    graph_node_id: str | None = None
    generation: ContentGenerationRunResponse
    validation_findings: list[str] = Field(default_factory=list)
    save_result: SaveLessonResult | None = None
    catalog_refresh_note: str = (
        "After publish/save, catalog refresh is enqueued by RPC (EF3 refresh-course-catalog)."
    )


def resolve_graph_node(
    graph_search: GraphSearchPort,
    *,
    tenant_id: str,
    course_slug: str,
    graph_node_id: str | None,
    graph_query: str | None,
    topic: str,
    graph_index: str | None = None,
) -> tuple[str | None, list[dict[str, Any]]]:
    known_uuid = graph_node_id_for_upsert(graph_node_id)
    if known_uuid:
        pinned_index = graph_index.strip() if isinstance(graph_index, str) else ""
        if pinned_index:
            hit = GraphNodeHit(
                node_id=known_uuid,
                label=topic,
                graph_index=pinned_index,
                course_slug=course_slug,
                kind="lesson",
                score=1.0,
            )
            return known_uuid, [hit.model_dump()]
        return known_uuid, []

    query = graph_query or topic
    hits = graph_search.search_graph_nodes(
        tenant_id=tenant_id,
        query=query,
        course_slug=course_slug,
    )
    serialized = [hit.model_dump() for hit in hits]
    if graph_node_id:
        return graph_node_id, serialized
    return None, serialized


async def run_author_lesson_pipeline(
    *,
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
    graph_search: GraphSearchPort,
    backend_factory: AuthoringBackendFactoryPort,
    job_progress: AiGenerationJobProgressPort | None = None,
) -> AuthorLessonPipelineResponse:
    """Orchestrate search → generate → validate → save → publish (graph-scoped)."""
    if job_id and job_progress is not None:
        existing = await load_succeeded_author_save_result(job_progress, job_id)
        if existing is not None:
            return AuthorLessonPipelineResponse(
                generation=ContentGenerationRunResponse(
                    topic=topic,
                    grade_level=grade_level,
                    generation_complete=True,
                    lesson_retry_count=0,
                    quiz_retry_count=0,
                    pbl_retry_count=0,
                ),
                save_result=existing,
            )
    progress = job_progress if job_id else None
    graph_index = graph_index.strip() if isinstance(graph_index, str) and graph_index.strip() else None
    try:
        if job_id:
            await report_ai_generation_job(
                progress,
                job_id=job_id,
                status="running",
            )
        resolved_node_id, graph_hits = await asyncio.to_thread(
            resolve_graph_node,
            graph_search,
            tenant_id=tenant_id,
            course_slug=course_slug,
            graph_node_id=graph_node_id,
            graph_query=graph_query,
            topic=topic,
            graph_index=graph_index,
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
            graph_hits=graph_hits,
            graph_index=graph_index,
        )
        generation = await invoke_content_generation(
            gen_request,
            graph_search=graph_search,
            job_id=job_id,
            job_progress=progress,
        )

        harness_lesson = generation.harness_lesson
        harness_quiz = generation.harness_quiz
        harness_project = generation.harness_project
        if harness_lesson is None:
            raise DomainValidationError(
                "Graph-scoped generation did not produce harness_lesson"
            )

        lesson_findings = validate_lesson_dict(harness_lesson)
        quiz_findings = validate_quiz_dict(harness_quiz) if harness_quiz else []
        project_findings = (
            validate_project_dict(harness_project, strict_readme_sections=False)
            if harness_project
            else []
        )
        findings: list[str] = [*lesson_findings, *quiz_findings, *project_findings]
        if any(item.startswith("error:") for item in lesson_findings):
            if job_id:
                first_error = next(item for item in lesson_findings if item.startswith("error:"))
                await report_ai_generation_job(
                    progress,
                    job_id=job_id,
                    status="failed",
                    error=first_error,
                )
            return AuthorLessonPipelineResponse(
                graph_hits=graph_hits,
                graph_node_id=resolved_node_id,
                generation=generation,
                validation_findings=findings,
            )
        quiz_to_save = (
            harness_quiz
            if harness_quiz and not any(item.startswith("error:") for item in quiz_findings)
            else None
        )
        project_to_save = (
            harness_project
            if harness_project and not any(item.startswith("error:") for item in project_findings)
            else None
        )

        if job_id:
            await report_ai_generation_job(
                progress,
                job_id=job_id,
                status="running",
                phase="save",
            )
        backend = backend_factory.for_jwt(manager_jwt)
        service = AuthoringService(backend)
        save_result = await service.save_lesson_bundle(
            module_id=module_id,
            lesson_slug=lesson_slug,
            lesson=harness_lesson,
            quiz=quiz_to_save,
            project=project_to_save,
            publish=publish,
            strict_project_readme_sections=False,
            graph_node_id=resolved_node_id,
        )
        if job_id:
            result_ref: dict[str, Any] = {"lesson_id": save_result.lesson_id}
            if save_result.quiz_id:
                result_ref["quiz_id"] = save_result.quiz_id
            if save_result.project_id:
                result_ref["project_id"] = save_result.project_id
            await report_ai_generation_job(
                progress,
                job_id=job_id,
                status="succeeded",
                result_ref=result_ref,
            )
        return AuthorLessonPipelineResponse(
            graph_hits=graph_hits,
            graph_node_id=resolved_node_id,
            generation=generation,
            validation_findings=findings,
            save_result=save_result,
        )
    except Exception:
        if job_id:
            await report_ai_generation_job(
                progress,
                job_id=job_id,
                status="failed",
                error=AUTHOR_PIPELINE_FAILED_ERROR,
            )
        raise
