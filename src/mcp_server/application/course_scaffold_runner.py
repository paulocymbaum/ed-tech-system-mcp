"""Orchestrate course-scaffold generation and optional job progress."""

from __future__ import annotations

from typing import Any

from mcp_server.application.agent import (
    ainvoke_with_workflow_timeout,
    workflow_timeout_seconds,
)
from mcp_server.application.agents.course_scaffold.graph import (
    get_course_scaffold_graph,
    initial_course_scaffold_state,
)
from mcp_server.application.author_job_progress import report_ai_generation_job
from mcp_server.application.workflow_trace import (
    GraphStreamComplete,
    WorkflowTraceStart,
    WorkflowTraceStep,
    stream_graph_with_trace,
)
from mcp_server.domain.ai_generation_job import (
    AiGenerationJobProgressPort,
    AiGenerationJobSnapshot,
)
from mcp_server.domain.course_scaffold import ScaffoldProposal, require_valid_scaffold_proposal
from mcp_server.domain.exceptions import DomainValidationError


async def load_succeeded_scaffold_proposal(
    port: AiGenerationJobProgressPort | None,
    job_id: str,
) -> ScaffoldProposal | None:
    """Return a succeeded job's proposal, or None. Fail-open."""
    if port is None:
        return None
    snapshot: AiGenerationJobSnapshot | None
    try:
        snapshot = await port.get(job_id)
    except Exception:
        return None
    if snapshot is None or snapshot.status != "succeeded":
        return None
    result_ref = snapshot.result_ref
    if not isinstance(result_ref, dict):
        return None
    nested = result_ref.get("proposal")
    raw: Any = nested if isinstance(nested, dict) else result_ref
    try:
        return require_valid_scaffold_proposal(ScaffoldProposal.model_validate(raw))
    except (DomainValidationError, Exception):
        return None


def _proposal_from_state(result: Any) -> ScaffoldProposal:
    if not isinstance(result, dict):
        raise DomainValidationError("Course scaffold generation failed")
    proposal = result.get("proposal")
    if not isinstance(proposal, ScaffoldProposal):
        errors = result.get("validation_errors") or ["Course scaffold generation failed"]
        message = "; ".join(str(item) for item in errors)
        raise DomainValidationError(message)
    require_valid_scaffold_proposal(proposal)
    return proposal


async def invoke_course_scaffold(
    *,
    tenant_id: str,
    prompt: str,
    title: str | None = None,
    locale: str | None = None,
    slug: str | None = None,
    course_slug: str | None = None,
    job_id: str | None = None,
    job_progress: AiGenerationJobProgressPort | None = None,
) -> ScaffoldProposal:
    """Run the course-scaffold graph. Does not apply the live course graph."""
    progress = job_progress if job_id else None
    if job_id:
        existing = await load_succeeded_scaffold_proposal(progress, job_id)
        if existing is not None:
            return existing
        await report_ai_generation_job(
            progress,
            job_id=job_id,
            status="running",
            phase="generate",
        )
    graph = get_course_scaffold_graph()
    state = initial_course_scaffold_state(
        tenant_id=tenant_id,
        prompt=prompt,
        title=title,
        locale=locale,
        slug=slug,
        course_slug=course_slug,
    )
    try:
        if job_id:
            final_state: Any = None
            async for item in stream_graph_with_trace(
                graph,
                state,
                timeout_seconds=workflow_timeout_seconds(),
            ):
                if isinstance(item, (WorkflowTraceStart, WorkflowTraceStep)):
                    await report_ai_generation_job(
                        progress,
                        job_id=job_id,
                        status="running",
                        phase="generate",
                    )
                elif isinstance(item, GraphStreamComplete):
                    final_state = item.state
            if final_state is None:
                raise DomainValidationError("Course scaffold generation failed")
            result = final_state
        else:
            result = await ainvoke_with_workflow_timeout(graph, state)
    except DomainValidationError as exc:
        if job_id:
            await report_ai_generation_job(
                progress,
                job_id=job_id,
                status="failed",
                error=str(exc),
            )
        raise
    except Exception:
        if job_id:
            await report_ai_generation_job(
                progress,
                job_id=job_id,
                status="failed",
                error="Course scaffold generation failed",
            )
        raise
    try:
        return _proposal_from_state(result)
    except DomainValidationError as exc:
        if job_id:
            await report_ai_generation_job(
                progress,
                job_id=job_id,
                status="failed",
                error=str(exc),
            )
        raise
