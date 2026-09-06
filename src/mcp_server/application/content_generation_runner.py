"""Graph-scoped content generation orchestration (E6.2)."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp_server.application.agent import (
    ainvoke_with_workflow_timeout,
    workflow_timeout_seconds,
)
from mcp_server.application.agents.content_generation.graph import (
    get_content_generation_graph,
    initial_content_generation_state,
)
from mcp_server.application.author_job_progress import (
    node_id_to_author_phase,
    report_ai_generation_job,
)
from mcp_server.application.content_generation_dtos import (
    ContentGenerationRunRequest,
    ContentGenerationRunResponse,
    content_generation_state_to_run_response,
)
from mcp_server.application.workflow_trace import (
    GraphStreamComplete,
    WorkflowTraceStart,
    WorkflowTraceStep,
    stream_graph_with_trace,
)
from mcp_server.domain.ai_generation_job import AiGenerationJobProgressPort
from mcp_server.domain.authoring import GraphNodeHit, GraphSearchPort


def _graph_hits_from_request(request: ContentGenerationRunRequest) -> list[GraphNodeHit]:
    if not request.graph_hits:
        return []
    hits: list[GraphNodeHit] = []
    for raw in request.graph_hits:
        if isinstance(raw, GraphNodeHit):
            hits.append(raw)
        elif isinstance(raw, dict):
            hits.append(GraphNodeHit.model_validate(raw))
    return hits


async def invoke_content_generation(
    request: ContentGenerationRunRequest,
    *,
    graph_search: GraphSearchPort | None = None,
    job_id: str | None = None,
    job_progress: AiGenerationJobProgressPort | None = None,
) -> ContentGenerationRunResponse:
    """Run content generation; graph-scoped when tenant_id + course_slug are set."""
    graph_hits: list[GraphNodeHit] = []
    resolved_node = request.graph_node_id
    if request.tenant_id and request.course_slug:
        if graph_search is None:
            msg = "Graph search repository is required for graph-scoped content generation"
            raise RuntimeError(msg)
        preloaded = _graph_hits_from_request(request)
        if preloaded:
            graph_hits = preloaded
        elif request.graph_query or not resolved_node:
            hits = await asyncio.to_thread(
                graph_search.search_graph_nodes,
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
            graph_index=request.graph_index,
        )
    else:
        state = initial_content_generation_state(
            request.topic,
            grade_level=request.grade_level,
        )

    graph = get_content_generation_graph()
    if not job_id:
        result = await ainvoke_with_workflow_timeout(graph, state)
        return content_generation_state_to_run_response(result)

    final_state: Any = None
    async for item in stream_graph_with_trace(
        graph,
        state,
        timeout_seconds=workflow_timeout_seconds(),
    ):
        if isinstance(item, (WorkflowTraceStart, WorkflowTraceStep)):
            phase = node_id_to_author_phase(item.node_id)
            if phase is not None:
                await report_ai_generation_job(
                    job_progress,
                    job_id=job_id,
                    status="running",
                    phase=phase,
                )
        elif isinstance(item, GraphStreamComplete):
            final_state = item.state
    if final_state is None:
        msg = "Content generation stream completed without a final state"
        raise RuntimeError(msg)
    return content_generation_state_to_run_response(final_state)


def graph_hits_to_dicts(hits: list[GraphNodeHit]) -> list[dict[str, Any]]:
    return [hit.model_dump() for hit in hits]
