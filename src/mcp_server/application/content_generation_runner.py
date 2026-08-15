"""Graph-scoped content generation orchestration (E6.2)."""

from __future__ import annotations

from typing import Any

from mcp_server.application.agent import workflow_timeout_seconds
from mcp_server.application.agents.content_generation.graph import (
    get_content_generation_graph,
    initial_content_generation_state,
)
from mcp_server.application.workflow_trace import invoke_graph_with_trace
from mcp_server.domain.authoring import GraphNodeHit, GraphSearchPort
from mcp_server.interface.validation_workflow import (
    ContentGenerationRunRequest,
    ContentGenerationRunResponse,
    content_generation_state_to_run_response,
)


async def invoke_content_generation(
    request: ContentGenerationRunRequest,
    *,
    graph_search: GraphSearchPort | None = None,
) -> ContentGenerationRunResponse:
    """Run content generation; graph-scoped when tenant_id + course_slug are set."""
    graph_hits: list[GraphNodeHit] = []
    resolved_node = request.graph_node_id
    if request.tenant_id and request.course_slug:
        if graph_search is None:
            msg = "Graph search repository is required for graph-scoped content generation"
            raise RuntimeError(msg)
        if request.graph_query or not resolved_node:
            hits = graph_search.search_graph_nodes(
                tenant_id=request.tenant_id,
                query=request.graph_query or request.topic,
                course_slug=request.course_slug,
            )
            graph_hits = hits
            if not resolved_node and hits:
                resolved_node = hits[0].node_id
        state = initial_content_generation_state(
            request.topic,
            grade_level=request.grade_level,
            tenant_id=request.tenant_id,
            course_slug=request.course_slug,
            module_id=request.module_id,
            lesson_slug=request.lesson_slug,
            graph_node_id=resolved_node,
            graph_hits=graph_hits,
        )
    else:
        state = initial_content_generation_state(
            request.topic,
            grade_level=request.grade_level,
        )

    graph = get_content_generation_graph()
    result, trace = await invoke_graph_with_trace(
        graph,
        state,
        timeout_seconds=workflow_timeout_seconds(),
    )
    return content_generation_state_to_run_response(result, trace=trace)


def graph_hits_to_dicts(hits: list[GraphNodeHit]) -> list[dict[str, Any]]:
    return [hit.model_dump() for hit in hits]
