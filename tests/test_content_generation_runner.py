"""Author pipeline should not repeat graph search when hits are preloaded."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.application.content_generation_runner import invoke_content_generation
from mcp_server.domain.authoring import GraphNodeHit
from mcp_server.interface.validation_workflow import ContentGenerationRunRequest


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
