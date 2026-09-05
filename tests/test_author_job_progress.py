"""Node → Teach UX phase mapping for author-pipeline job progress."""

from __future__ import annotations

from typing import Any

import pytest

from mcp_server.application.author_job_progress import (
    load_succeeded_author_lesson_id,
    node_id_to_author_phase,
)
from mcp_server.domain.ai_generation_job import (
    AiGenerationJobProgressPort,
    AiGenerationJobSnapshot,
)


class _FakeGetPort(AiGenerationJobProgressPort):
    def __init__(
        self,
        snapshot: AiGenerationJobSnapshot | None = None,
        *,
        get_error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.get_error = get_error

    async def get(self, job_id: str) -> AiGenerationJobSnapshot | None:
        if self.get_error is not None:
            raise self.get_error
        return self.snapshot

    async def update(
        self,
        *,
        job_id: str,
        status: str | None = None,
        phase: str | None = None,
        error: str | None = None,
        result_ref: dict[str, Any] | None = None,
    ) -> None:
        return None


def test_node_id_to_author_phase_maps_lesson_quiz_project() -> None:
    assert node_id_to_author_phase("generate_lesson") == "readme"
    assert node_id_to_author_phase("validate_lesson") == "readme"
    assert node_id_to_author_phase("generate_quiz") == "quiz"
    assert node_id_to_author_phase("validate_quiz") == "quiz"
    assert node_id_to_author_phase("generate_pbl") == "project"
    assert node_id_to_author_phase("validate_pbl") == "project"
    assert node_id_to_author_phase("merge_results") == "project"


def test_node_id_to_author_phase_ignores_unknown_nodes() -> None:
    assert node_id_to_author_phase("save_lesson_bundle") is None
    assert node_id_to_author_phase("unknown") is None


@pytest.mark.asyncio
async def test_load_succeeded_author_lesson_id_requires_succeeded_and_lesson() -> None:
    ok = _FakeGetPort(
        AiGenerationJobSnapshot(
            status="succeeded",
            result_ref={"lesson_id": "les-1"},
        )
    )
    running = _FakeGetPort(AiGenerationJobSnapshot(status="running"))
    missing_id = _FakeGetPort(
        AiGenerationJobSnapshot(status="succeeded", result_ref={})
    )
    exploding = _FakeGetPort(get_error=RuntimeError("boom"))

    assert await load_succeeded_author_lesson_id(ok, "job-1") == "les-1"
    assert await load_succeeded_author_lesson_id(running, "job-1") is None
    assert await load_succeeded_author_lesson_id(missing_id, "job-1") is None
    assert await load_succeeded_author_lesson_id(exploding, "job-1") is None
    assert await load_succeeded_author_lesson_id(None, "job-1") is None
