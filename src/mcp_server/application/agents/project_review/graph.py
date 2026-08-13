"""Compile and run the project-review LangGraph workflow (E7)."""

from __future__ import annotations

from typing import Literal, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from mcp_server.application.agents.project_review.nodes import (
    collect_context,
    grade_delivery,
    persist_grade,
    validate_grade,
)
from mcp_server.application.agents.project_review.state import ProjectReviewState
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)
from mcp_server.application.workflow_trace import invoke_graph_with_trace
from mcp_server.domain.project_review import ProjectReviewResult

ProjectReviewGraph = CompiledStateGraph[
    ProjectReviewState, ProjectReviewState, ProjectReviewState
]

_graph: ProjectReviewGraph | None = None


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def _route_after_validate(
    state: ProjectReviewState,
) -> Literal["grade_delivery", "persist_grade"]:
    errors = state.get("validation_errors") or []
    retries = int(state.get("grade_retry_count") or 0)
    if errors and retries < 1 and state.get("score") is not None:
        return "grade_delivery"
    return "persist_grade"


def build_project_review_graph() -> ProjectReviewGraph:
    graph: StateGraph[ProjectReviewState, ProjectReviewState, ProjectReviewState] = StateGraph(
        ProjectReviewState
    )
    config = _workflow_runtime_config()
    retry = RetryPolicy(max_attempts=max(config.node_retries + 1, 1))
    timeout = config.agent_node_timeout_seconds

    graph.add_node("collect_context", collect_context, timeout=timeout)
    graph.add_node(
        "grade_delivery",
        grade_delivery,
        retry_policy=retry,
        timeout=timeout,
    )
    graph.add_node("validate_grade", validate_grade, timeout=timeout)
    graph.add_node("persist_grade", persist_grade, timeout=timeout)

    graph.add_edge(START, "collect_context")
    graph.add_edge("collect_context", "grade_delivery")
    graph.add_edge("grade_delivery", "validate_grade")
    graph.add_conditional_edges("validate_grade", _route_after_validate)
    graph.add_edge("persist_grade", END)
    return cast(ProjectReviewGraph, graph.compile())


def get_project_review_graph() -> ProjectReviewGraph:
    global _graph
    if _graph is None:
        _graph = build_project_review_graph()
    return _graph


def reset_project_review_graph_cache() -> None:
    global _graph
    _graph = None


def initial_project_review_state(
    *,
    tenant_id: str,
    course_slug: str,
    module_slug: str,
    lesson_slug: str,
    project_slug: str,
    user_id: str,
    delivery_limit: int = 3,
    persist: bool = True,
) -> ProjectReviewState:
    return {
        "tenant_id": tenant_id,
        "course_slug": course_slug,
        "module_slug": module_slug,
        "lesson_slug": lesson_slug,
        "project_slug": project_slug,
        "user_id": user_id,
        "delivery_limit": delivery_limit,
        "persist": persist,
        "context": None,
        "score": None,
        "comment": None,
        "validation_errors": [],
        "grade_retry_count": 0,
        "result": None,
        "model_id": None,
        "error": None,
        "llm_io": [],
    }


async def run_project_review_graph(**kwargs: object) -> tuple[ProjectReviewState, object]:
    from mcp_server.application.agent import workflow_timeout_seconds

    graph = get_project_review_graph()
    state = initial_project_review_state(
        tenant_id=str(kwargs["tenant_id"]),
        course_slug=str(kwargs["course_slug"]),
        module_slug=str(kwargs["module_slug"]),
        lesson_slug=str(kwargs["lesson_slug"]),
        project_slug=str(kwargs["project_slug"]),
        user_id=str(kwargs["user_id"]),
        delivery_limit=int(kwargs.get("delivery_limit") or 3),
        persist=bool(kwargs.get("persist", True)),
    )
    return await invoke_graph_with_trace(
        graph,
        state,
        timeout_seconds=workflow_timeout_seconds(),
    )


def result_from_state(state: ProjectReviewState) -> ProjectReviewResult:
    result = state.get("result")
    if result is not None:
        return result
    context = state.get("context")
    delivery_id = context.latest_delivery_id if context else ""
    score = int(state.get("score") or 0)
    comment = str(state.get("comment") or state.get("error") or "Review failed")
    return ProjectReviewResult(
        score=score,
        comment=comment[:480],
        passed=score > 80,
        delivery_id=delivery_id or "",
        persisted=False,
        model_id=state.get("model_id"),
    )
