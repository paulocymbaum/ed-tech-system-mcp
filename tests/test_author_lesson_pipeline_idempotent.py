"""JB-015: skip generate/save when the author job already succeeded."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.application.content_generation_dtos import ContentGenerationRunResponse
from mcp_server.domain.ai_generation_job import (
    AiGenerationJobProgressPort,
    AiGenerationJobSnapshot,
)
from mcp_server.domain.authoring import (
    AuthoringBackendFactoryPort,
    AuthoringBackendPort,
    GraphNodeHit,
    GraphSearchPort,
    SaveLessonResult,
)
from mcp_server.interface.custom_tools_authoring import (
    author_lesson_pipeline,
    register_authoring_tools,
)

_PIPELINE_ARGS = {
    "manager_jwt": "jwt",
    "tenant_id": "00000000-0000-4000-8000-000000000001",
    "course_slug": "javascript",
    "module_id": "00000000-0000-4000-8000-000000000010",
    "topic": "variables",
    "lesson_slug": "01-variables",
    "grade_level": "6th grade",
}

_SUCCEEDED_LESSON = "11111111-1111-4111-8111-111111111111"


class FakeGraphSearch(GraphSearchPort):
    def search_graph_nodes(
        self,
        *,
        tenant_id: str,
        query: str,
        course_slug: str | None = None,
        min_similarity: float = 0.1,
        limit: int = 5,
    ) -> list[GraphNodeHit]:
        return []


class FakeBackendFactory(AuthoringBackendFactoryPort):
    def for_jwt(self, manager_jwt: str) -> AuthoringBackendPort:
        return MagicMock()


class FakeJobProgress(AiGenerationJobProgressPort):
    def __init__(
        self,
        snapshot: AiGenerationJobSnapshot | None = None,
        *,
        get_error: Exception | None = None,
    ) -> None:
        self.snapshot = snapshot
        self.get_error = get_error
        self.get_calls: list[str] = []
        self.update_calls: list[dict[str, Any]] = []

    async def get(self, job_id: str) -> AiGenerationJobSnapshot | None:
        self.get_calls.append(job_id)
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
        self.update_calls.append(
            {
                "job_id": job_id,
                "status": status,
                "phase": phase,
                "error": error,
                "result_ref": result_ref,
            }
        )


def _generation() -> ContentGenerationRunResponse:
    return ContentGenerationRunResponse(
        topic="variables",
        grade_level="6th grade",
        generation_complete=True,
        lesson_retry_count=0,
        quiz_retry_count=0,
        pbl_retry_count=0,
        harness_lesson={"title": "Variables", "readme": "# Variables\n"},
    )


def _pass_validation() -> tuple[Any, Any]:
    return (
        patch(
            "mcp_server.application.author_lesson_pipeline.validate_lesson_dict",
            return_value=[],
        ),
        patch(
            "mcp_server.application.author_lesson_pipeline.validate_quiz_dict",
            return_value=[],
        ),
    )


@pytest.mark.asyncio
async def test_succeeded_job_skips_generate_and_save() -> None:
    progress = FakeJobProgress(
        AiGenerationJobSnapshot(
            status="succeeded",
            result_ref={
                "lesson_id": _SUCCEEDED_LESSON,
                "quiz_id": "quiz-1",
                "project_id": "proj-1",
            },
        )
    )
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=progress,
    )
    invoke = AsyncMock(side_effect=AssertionError("invoke_content_generation"))
    save = AsyncMock(side_effect=AssertionError("save_lesson_bundle"))

    with (
        patch(
            "mcp_server.application.author_lesson_pipeline.invoke_content_generation",
            invoke,
        ),
        patch(
            "mcp_server.application.authoring_service.AuthoringService.save_lesson_bundle",
            save,
        ),
    ):
        response = await author_lesson_pipeline(
            **_PIPELINE_ARGS,
            job_id="22222222-2222-4222-8222-222222222222",
        )

    assert invoke.await_count == 0
    assert save.await_count == 0
    assert progress.get_calls == ["22222222-2222-4222-8222-222222222222"]
    assert progress.update_calls == []
    assert response.save_result is not None
    assert response.save_result.lesson_id == _SUCCEEDED_LESSON
    assert response.save_result.quiz_id == "quiz-1"
    assert response.save_result.project_id == "proj-1"
    assert response.generation.generation_complete is True
    assert response.generation.topic == "variables"
    assert response.generation.grade_level == "6th grade"
    assert response.generation.harness_lesson is None


@pytest.mark.asyncio
async def test_omitted_job_id_does_not_call_get() -> None:
    progress = FakeJobProgress(
        AiGenerationJobSnapshot(
            status="succeeded",
            result_ref={"lesson_id": _SUCCEEDED_LESSON},
        )
    )
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=progress,
    )
    invoke = AsyncMock(return_value=_generation())
    save = AsyncMock(
        return_value=SaveLessonResult(lesson_id="new-lesson"),
    )

    lesson_val, quiz_val = _pass_validation()
    with (
        patch(
            "mcp_server.application.author_lesson_pipeline.invoke_content_generation",
            invoke,
        ),
        patch(
            "mcp_server.application.authoring_service.AuthoringService.save_lesson_bundle",
            save,
        ),
        lesson_val,
        quiz_val,
    ):
        response = await author_lesson_pipeline(**_PIPELINE_ARGS)

    assert progress.get_calls == []
    assert invoke.await_count == 1
    assert save.await_count == 1
    assert response.save_result is not None
    assert response.save_result.lesson_id == "new-lesson"


@pytest.mark.asyncio
async def test_running_job_follows_generate_save_path() -> None:
    progress = FakeJobProgress(AiGenerationJobSnapshot(status="running"))
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=progress,
    )
    invoke = AsyncMock(return_value=_generation())
    save = AsyncMock(return_value=SaveLessonResult(lesson_id="fresh-lesson"))

    lesson_val, quiz_val = _pass_validation()
    with (
        patch(
            "mcp_server.application.author_lesson_pipeline.invoke_content_generation",
            invoke,
        ),
        patch(
            "mcp_server.application.authoring_service.AuthoringService.save_lesson_bundle",
            save,
        ),
        lesson_val,
        quiz_val,
    ):
        response = await author_lesson_pipeline(
            **_PIPELINE_ARGS,
            job_id="33333333-3333-4333-8333-333333333333",
        )

    assert invoke.await_count == 1
    assert save.await_count == 1
    assert response.save_result is not None
    assert response.save_result.lesson_id == "fresh-lesson"
    assert [c["status"] for c in progress.update_calls][-1] == "succeeded"
    assert progress.update_calls[-1]["result_ref"] == {"lesson_id": "fresh-lesson"}


@pytest.mark.asyncio
async def test_save_result_ref_includes_quiz_and_project_ids() -> None:
    progress = FakeJobProgress(AiGenerationJobSnapshot(status="running"))
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=progress,
    )
    invoke = AsyncMock(return_value=_generation())
    save = AsyncMock(
        return_value=SaveLessonResult(
            lesson_id="fresh-lesson",
            quiz_id="quiz-9",
            project_id="proj-9",
        )
    )
    job_id = "55555555-5555-4555-8555-555555555555"

    lesson_val, quiz_val = _pass_validation()
    with (
        patch(
            "mcp_server.application.author_lesson_pipeline.invoke_content_generation",
            invoke,
        ),
        patch(
            "mcp_server.application.authoring_service.AuthoringService.save_lesson_bundle",
            save,
        ),
        lesson_val,
        quiz_val,
    ):
        await author_lesson_pipeline(**_PIPELINE_ARGS, job_id=job_id)

    succeeded = [c for c in progress.update_calls if c["status"] == "succeeded"]
    assert succeeded[-1]["result_ref"] == {
        "lesson_id": "fresh-lesson",
        "quiz_id": "quiz-9",
        "project_id": "proj-9",
    }


@pytest.mark.asyncio
async def test_validation_errors_report_failed_without_save() -> None:
    progress = FakeJobProgress(AiGenerationJobSnapshot(status="running"))
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=progress,
    )
    invoke = AsyncMock(return_value=_generation())
    save = AsyncMock(side_effect=AssertionError("save_lesson_bundle"))
    job_id = "44444444-4444-4444-8444-444444444444"

    with (
        patch(
            "mcp_server.application.author_lesson_pipeline.invoke_content_generation",
            invoke,
        ),
        patch(
            "mcp_server.application.authoring_service.AuthoringService.save_lesson_bundle",
            save,
        ),
        patch(
            "mcp_server.application.author_lesson_pipeline.validate_lesson_dict",
            return_value=["error: missing objectives", "warn: thin quiz"],
        ),
        patch(
            "mcp_server.application.author_lesson_pipeline.validate_quiz_dict",
            return_value=[],
        ),
    ):
        response = await author_lesson_pipeline(**_PIPELINE_ARGS, job_id=job_id)

    assert invoke.await_count == 1
    assert save.await_count == 0
    assert response.save_result is None
    assert response.validation_findings == [
        "error: missing objectives",
        "warn: thin quiz",
    ]
    failed = [c for c in progress.update_calls if c["status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["job_id"] == job_id
    assert failed[0]["error"] == "error: missing objectives"
    assert not any(c["status"] == "succeeded" for c in progress.update_calls)


@pytest.mark.asyncio
async def test_validation_errors_without_job_id_do_not_write_progress() -> None:
    progress = FakeJobProgress()
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=progress,
    )
    invoke = AsyncMock(return_value=_generation())
    save = AsyncMock(side_effect=AssertionError("save_lesson_bundle"))

    with (
        patch(
            "mcp_server.application.author_lesson_pipeline.invoke_content_generation",
            invoke,
        ),
        patch(
            "mcp_server.application.authoring_service.AuthoringService.save_lesson_bundle",
            save,
        ),
        patch(
            "mcp_server.application.author_lesson_pipeline.validate_lesson_dict",
            return_value=["error: empty readme"],
        ),
    ):
        response = await author_lesson_pipeline(**_PIPELINE_ARGS)

    assert save.await_count == 0
    assert progress.get_calls == []
    assert progress.update_calls == []
    assert response.save_result is None
    assert response.validation_findings == ["error: empty readme"]


@pytest.mark.asyncio
async def test_quiz_errors_do_not_block_readme_save() -> None:
    progress = FakeJobProgress(AiGenerationJobSnapshot(status="running"))
    register_authoring_tools(
        graph_search=FakeGraphSearch(),
        backend_factory=FakeBackendFactory(),
        job_progress=progress,
    )
    generation = _generation()
    generation.harness_quiz = {"id": "q", "title": "Quiz", "questions": []}
    invoke = AsyncMock(return_value=generation)
    save = AsyncMock(
        return_value=SaveLessonResult(
            lesson_id="saved-lesson",
            quiz_id=None,
            project_id=None,
            published=False,
        )
    )
    job_id = "55555555-5555-4555-8555-555555555555"

    with (
        patch(
            "mcp_server.application.author_lesson_pipeline.invoke_content_generation",
            invoke,
        ),
        patch(
            "mcp_server.application.authoring_service.AuthoringService.save_lesson_bundle",
            save,
        ),
        patch(
            "mcp_server.application.author_lesson_pipeline.validate_lesson_dict",
            return_value=[],
        ),
        patch(
            "mcp_server.application.author_lesson_pipeline.validate_quiz_dict",
            return_value=["error: options must contain exactly 4 entries"],
        ),
    ):
        response = await author_lesson_pipeline(**_PIPELINE_ARGS, job_id=job_id)

    assert save.await_count == 1
    assert save.await_args.kwargs["quiz"] is None
    assert save.await_args.kwargs["project"] is None
    assert response.save_result is not None
    assert response.save_result.lesson_id == "saved-lesson"
    assert "error: options must contain exactly 4 entries" in response.validation_findings
    succeeded = [c for c in progress.update_calls if c["status"] == "succeeded"]
    assert succeeded[-1]["result_ref"] == {"lesson_id": "saved-lesson"}
