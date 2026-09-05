"""JB-008: project_review consumes optional job_id via the Slice 1 progress port."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.domain.ai_generation_job import (
    AiGenerationJobProgressPort,
    AiGenerationJobSnapshot,
)
from mcp_server.domain.exceptions import ExternalServiceError
from mcp_server.domain.project_review import ProjectReviewResult
from mcp_server.interface.custom_tools_project_review import (
    PROJECT_REVIEW_FAILED_ERROR,
    project_review,
    register_project_review_tool_repository,
)

_REVIEW_ARGS = {
    "tenant_id": "00000000-0000-4000-8000-000000000001",
    "course_slug": "javascript",
    "module_slug": "mod",
    "lesson_slug": "lesson",
    "project_slug": "proj",
    "user_id": "00000000-0000-4000-8000-000000000002",
}

_SUCCESS = ProjectReviewResult(
    score=91,
    comment="The submission meets the README and includes working tests.",
    passed=True,
    delivery_id="del-1",
    review_id="rev-1",
    persisted=True,
)


class FakeJobProgress(AiGenerationJobProgressPort):
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def get(self, job_id: str) -> AiGenerationJobSnapshot | None:
        return None

    async def update(
        self,
        *,
        job_id: str,
        status: str | None = None,
        phase: str | None = None,
        error: str | None = None,
        result_ref: dict[str, Any] | None = None,
    ) -> None:
        self.calls.append(
            {
                "job_id": job_id,
                "status": status,
                "phase": phase,
                "error": error,
                "result_ref": result_ref,
            }
        )


@pytest.fixture
def port() -> FakeJobProgress:
    progress = FakeJobProgress()
    register_project_review_tool_repository(MagicMock(), job_progress=progress)
    return progress


def _graph_patches(ainvoke: AsyncMock) -> tuple[Any, Any]:
    return (
        patch(
            "mcp_server.interface.custom_tools_project_review.get_project_review_graph",
            return_value=MagicMock(),
        ),
        patch(
            "mcp_server.interface.custom_tools_project_review.ainvoke_with_workflow_timeout",
            ainvoke,
        ),
    )


@pytest.mark.asyncio
async def test_project_review_without_job_id_uses_cache_and_skips_port(
    port: FakeJobProgress,
) -> None:
    ainvoke = AsyncMock(return_value={"result": _SUCCESS, "error": None})

    async def passthrough(_name: str, _args: dict[str, object], invoker: Any) -> Any:
        return await invoker()

    cached = AsyncMock(side_effect=passthrough)
    graph_p, invoke_p = _graph_patches(ainvoke)
    with graph_p, invoke_p, patch(
        "mcp_server.interface.custom_tools_project_review._cached_tool_invoke",
        cached,
    ):
        result = await project_review(**_REVIEW_ARGS)

    assert result.score == 91
    cached.assert_awaited_once()
    assert port.calls == []
    ainvoke.assert_awaited_once()


@pytest.mark.asyncio
async def test_project_review_with_job_id_marks_running_then_succeeded(
    port: FakeJobProgress,
) -> None:
    ainvoke = AsyncMock(return_value={"result": _SUCCESS, "error": None})
    cached = AsyncMock()
    graph_p, invoke_p = _graph_patches(ainvoke)
    with graph_p, invoke_p, patch(
        "mcp_server.interface.custom_tools_project_review._cached_tool_invoke",
        cached,
    ):
        result = await project_review(
            **_REVIEW_ARGS,
            job_id="00000000-0000-4000-8000-000000000099",
        )

    assert result.review_id == "rev-1"
    cached.assert_not_called()
    assert [c["status"] for c in port.calls] == ["running", "succeeded"]
    assert all(c["phase"] is None for c in port.calls)
    assert port.calls[1]["result_ref"] == {
        "score": 91,
        "comment": _SUCCESS.comment,
        "delivery_id": "del-1",
        "review_id": "rev-1",
        "passed": True,
    }


@pytest.mark.asyncio
async def test_project_review_with_job_id_marks_failed_and_reraises(
    port: FakeJobProgress,
) -> None:
    ainvoke = AsyncMock(side_effect=ExternalServiceError("AI reviewer is temporarily unavailable"))
    graph_p, invoke_p = _graph_patches(ainvoke)
    with graph_p, invoke_p, pytest.raises(ExternalServiceError, match="temporarily unavailable"):
        await project_review(
            **_REVIEW_ARGS,
            job_id="00000000-0000-4000-8000-000000000099",
        )

    assert [c["status"] for c in port.calls] == ["running", "failed"]
    assert port.calls[1]["error"] == PROJECT_REVIEW_FAILED_ERROR
    assert port.calls[1]["phase"] is None
    assert port.calls[1]["result_ref"] is None
