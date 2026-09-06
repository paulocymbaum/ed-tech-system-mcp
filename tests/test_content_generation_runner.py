"""Author pipeline should not repeat graph search when hits are preloaded."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.application.content_generation_dtos import ContentGenerationRunRequest
from mcp_server.application.content_generation_runner import invoke_content_generation
from mcp_server.application.workflow_trace import (
    GraphStreamComplete,
    WorkflowTraceStart,
    WorkflowTraceStep,
)
from mcp_server.domain.authoring import GraphNodeHit


@pytest.mark.asyncio
async def test_invoke_content_generation_skips_search_when_graph_hits_preloaded() -> None:
    graph_search = MagicMock()
    hit = GraphNodeHit(
        node_id="node-1",
        course_slug="javascript",
        course_title="JS",
        label="Comments",
        graph_index="1.2.3",
        kind="lesson",
        score=1.0,
    )
    request = ContentGenerationRunRequest(
        topic="Comments",
        tenant_id="00000000-0000-4000-8000-000000000001",
        course_slug="javascript",
        module_id="00000000-0000-4000-8000-000000000002",
        lesson_slug="comments",
        graph_node_id="node-1",
        graph_query="comments",
        graph_hits=[hit.model_dump()],
    )

    with patch(
        "mcp_server.application.content_generation_runner.ainvoke_with_workflow_timeout",
        new_callable=AsyncMock,
    ) as mock_invoke:
        mock_invoke.return_value = {
            "topic": "Comments",
            "grade_level": "6th grade",
            "graph_scoped": True,
            "generation_complete": True,
        }
        response = await invoke_content_generation(request, graph_search=graph_search)

    graph_search.search_graph_nodes.assert_not_called()
    assert response.generation_complete is True


@pytest.mark.asyncio
async def test_invoke_content_generation_stream_steps_call_job_port() -> None:
    request = ContentGenerationRunRequest(topic="Comments")
    port = AsyncMock()
    ainvoke = AsyncMock()

    async def fake_stream(*_args: object, **_kwargs: object):
        yield WorkflowTraceStart(node_id="generate_lesson")
        yield WorkflowTraceStep(
            step=1,
            node_id="generate_lesson",
            status="ok",
            attempt=1,
        )
        yield WorkflowTraceStep(
            step=2,
            node_id="validate_quiz",
            status="ok",
            attempt=1,
        )
        yield WorkflowTraceStep(
            step=3,
            node_id="unknown_node",
            status="ok",
            attempt=1,
        )
        yield GraphStreamComplete(
            state={
                "topic": "Comments",
                "grade_level": "6th grade",
                "generation_complete": True,
            },
            trace=[],
        )

    with (
        patch(
            "mcp_server.application.content_generation_runner.get_content_generation_graph",
            return_value=MagicMock(),
        ),
        patch(
            "mcp_server.application.content_generation_runner.stream_graph_with_trace",
            fake_stream,
        ),
        patch(
            "mcp_server.application.content_generation_runner.ainvoke_with_workflow_timeout",
            ainvoke,
        ),
    ):
        response = await invoke_content_generation(
            request,
            job_id="00000000-0000-4000-8000-000000000099",
            job_progress=port,
        )

    ainvoke.assert_not_called()
    assert response.generation_complete is True
    assert port.update.await_count == 3
    first = port.update.await_args_list[0].kwargs
    second = port.update.await_args_list[1].kwargs
    third = port.update.await_args_list[2].kwargs
    assert first["phase"] == "readme"
    assert first["status"] == "running"
    assert first["job_id"] == "00000000-0000-4000-8000-000000000099"
    assert second["phase"] == "readme"
    assert third["phase"] == "quiz"
