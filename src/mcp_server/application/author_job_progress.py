"""Map content-generation nodes to Teach UX phases and report job progress."""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.domain.ai_generation_job import (
    AiGenerationJobProgressPort,
    AiGenerationJobSnapshot,
)
from mcp_server.domain.authoring import SaveLessonResult

logger = logging.getLogger(__name__)

AUTHOR_PIPELINE_FAILED_ERROR = "Author pipeline failed"

_NODE_PHASES: dict[str, str] = {
    "generate_lesson": "readme",
    "validate_lesson": "readme",
    "generate_quiz": "quiz",
    "validate_quiz": "quiz",
    "generate_pbl": "project",
    "validate_pbl": "project",
    "merge_results": "project",
}


def node_id_to_author_phase(node_id: str) -> str | None:
    """Return the Teach UX phase for a content-generation node, if any."""
    return _NODE_PHASES.get(node_id)


async def report_ai_generation_job(
    port: AiGenerationJobProgressPort | None,
    *,
    job_id: str,
    status: str | None = None,
    phase: str | None = None,
    error: str | None = None,
    result_ref: dict[str, Any] | None = None,
) -> None:
    """Call the job-progress port. Fail-open: log and continue on write errors."""
    if port is None:
        return
    try:
        await port.update(
            job_id=job_id,
            status=status,
            phase=phase,
            error=error,
            result_ref=result_ref,
        )
    except Exception:
        logger.warning("ai generation job progress update failed")


def _optional_result_id(result_ref: dict[str, Any], key: str) -> str | None:
    value = result_ref.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


async def _load_job_snapshot(
    port: AiGenerationJobProgressPort | None,
    job_id: str,
) -> AiGenerationJobSnapshot | None:
    if port is None:
        return None
    try:
        return await port.get(job_id)
    except Exception:
        logger.warning("ai generation job progress get failed")
        return None


async def load_succeeded_author_lesson_id(
    port: AiGenerationJobProgressPort | None,
    job_id: str,
) -> str | None:
    """Return ``result_ref.lesson_id`` when the job already succeeded. Fail-open."""
    save_result = await load_succeeded_author_save_result(port, job_id)
    return None if save_result is None else save_result.lesson_id


async def load_succeeded_author_save_result(
    port: AiGenerationJobProgressPort | None,
    job_id: str,
) -> SaveLessonResult | None:
    """Build ``SaveLessonResult`` from a succeeded job, or ``None``. Fail-open."""
    snapshot = await _load_job_snapshot(port, job_id)
    if snapshot is None or snapshot.status != "succeeded":
        return None
    result_ref = snapshot.result_ref
    if not isinstance(result_ref, dict):
        return None
    lesson_id = _optional_result_id(result_ref, "lesson_id")
    if lesson_id is None:
        return None
    return SaveLessonResult(
        lesson_id=lesson_id,
        quiz_id=_optional_result_id(result_ref, "quiz_id"),
        project_id=_optional_result_id(result_ref, "project_id"),
    )
