"""Compile and run the course-scaffold LangGraph workflow."""

from __future__ import annotations

from typing import Literal, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from mcp_server.application.agents.course_scaffold.nodes import (
    generate,
    max_validation_retries,
    validate,
)
from mcp_server.application.agents.course_scaffold.state import CourseScaffoldState
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)

CourseScaffoldGraph = CompiledStateGraph[
    CourseScaffoldState, CourseScaffoldState, CourseScaffoldState
]


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def _node_retry_policy() -> RetryPolicy:
    config = _workflow_runtime_config()
    max_attempts = max(config.node_retries + 1, 1)
    return RetryPolicy(max_attempts=max_attempts)


def _node_timeout_seconds() -> float:
    return _workflow_runtime_config().agent_node_timeout_seconds


def _route_after_validate(
    state: CourseScaffoldState,
) -> Literal["generate", "__end__"]:
    if state.get("proposal") is not None:
        return "__end__"
    if state.get("generate_retry_count", 0) <= max_validation_retries():
        return "generate"
    return "__end__"


def build_course_scaffold_graph() -> CourseScaffoldGraph:
    """Build generate → validate (with retry) for local UI visualization."""
    graph: StateGraph[CourseScaffoldState, CourseScaffoldState, CourseScaffoldState] = (
        StateGraph(CourseScaffoldState)
    )
    node_timeout = _node_timeout_seconds()
    graph.add_node(
        "generate",
        generate,
        retry_policy=_node_retry_policy(),
        timeout=node_timeout,
    )
    graph.add_node("validate", validate, timeout=node_timeout)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", "validate")
    graph.add_conditional_edges(
        "validate",
        _route_after_validate,
        {"generate": "generate", "__end__": END},
    )
    return graph.compile()


_COMPILED_GRAPH: CourseScaffoldGraph | None = None


def _get_compiled_graph() -> CourseScaffoldGraph:
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_course_scaffold_graph()
    return _COMPILED_GRAPH


def reset_course_scaffold_graph_cache() -> None:
    """Clear the memoized compiled graph (for tests)."""
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def initial_course_scaffold_state(
    *,
    tenant_id: str,
    prompt: str,
    title: str | None = None,
    locale: str | None = None,
    slug: str | None = None,
    course_slug: str | None = None,
) -> CourseScaffoldState:
    """Build the initial graph state for course scaffold generation."""
    return CourseScaffoldState(
        tenant_id=tenant_id,
        prompt=prompt,
        title=title,
        locale=locale,
        slug=slug,
        course_slug=course_slug,
        generate_retry_count=0,
        generation_complete=False,
    )


async def run_course_scaffold_graph(
    *,
    tenant_id: str,
    prompt: str,
    title: str | None = None,
    locale: str | None = None,
    slug: str | None = None,
    course_slug: str | None = None,
    config: RunnableConfig | None = None,
) -> CourseScaffoldState:
    """Run the course-scaffold graph with workflow timeout enforcement."""
    from mcp_server.application.agent import ainvoke_with_workflow_timeout

    graph = _get_compiled_graph()
    state = initial_course_scaffold_state(
        tenant_id=tenant_id,
        prompt=prompt,
        title=title,
        locale=locale,
        slug=slug,
        course_slug=course_slug,
    )
    result = await ainvoke_with_workflow_timeout(graph, state, config=config)
    return cast(CourseScaffoldState, result)


def get_course_scaffold_graph() -> CourseScaffoldGraph:
    """Return the memoized course-scaffold graph for workflow registration."""
    return _get_compiled_graph()
