"""Compile and run the content-generation LangGraph workflow."""

from __future__ import annotations

from typing import Literal, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from mcp_server.application.agents.content_generation.nodes import (
    generate_lesson,
    generate_pbl,
    generate_quiz,
    max_validation_retries,
    merge_results,
    validate_lesson,
    validate_pbl,
    validate_quiz,
)
from mcp_server.application.agents.content_generation.state import ContentGenerationState
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)

ContentGenerationGraph = CompiledStateGraph[
    ContentGenerationState, ContentGenerationState, ContentGenerationState
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


def _route_after_validate_lesson(
    state: ContentGenerationState,
) -> Literal["generate_lesson", "generate_quiz", "merge_results"]:
    if state.get("lesson") is not None:
        return "generate_quiz"
    if state.get("lesson_retry_count", 0) <= max_validation_retries():
        return "generate_lesson"
    return "merge_results"


def _route_after_validate_quiz(
    state: ContentGenerationState,
) -> Literal["generate_quiz", "generate_pbl", "merge_results"]:
    if state.get("quiz") is not None:
        return "generate_pbl"
    if state.get("quiz_retry_count", 0) <= max_validation_retries():
        return "generate_quiz"
    return "merge_results"


def _route_after_validate_pbl(
    state: ContentGenerationState,
) -> Literal["generate_pbl", "merge_results"]:
    if state.get("pbl") is not None:
        return "merge_results"
    if state.get("pbl_retry_count", 0) <= max_validation_retries():
        return "generate_pbl"
    return "merge_results"


def build_content_generation_graph() -> ContentGenerationGraph:
    """Build the lesson → quiz + PBL LangGraph for local UI visualization."""
    graph: StateGraph[
        ContentGenerationState, ContentGenerationState, ContentGenerationState
    ] = StateGraph(ContentGenerationState)
    llm_retry_policy = _node_retry_policy()
    node_timeout = _node_timeout_seconds()

    graph.add_node(
        "generate_lesson",
        generate_lesson,
        retry_policy=llm_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node("validate_lesson", validate_lesson, timeout=node_timeout)
    graph.add_node(
        "generate_quiz",
        generate_quiz,
        retry_policy=llm_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node("validate_quiz", validate_quiz, timeout=node_timeout)
    graph.add_node(
        "generate_pbl",
        generate_pbl,
        retry_policy=llm_retry_policy,
        timeout=node_timeout,
    )
    graph.add_node("validate_pbl", validate_pbl, timeout=node_timeout)
    graph.add_node("merge_results", merge_results, timeout=node_timeout)

    graph.add_edge(START, "generate_lesson")
    graph.add_edge("generate_lesson", "validate_lesson")
    graph.add_conditional_edges(
        "validate_lesson",
        _route_after_validate_lesson,
        {
            "generate_lesson": "generate_lesson",
            "generate_quiz": "generate_quiz",
            "merge_results": "merge_results",
        },
    )
    graph.add_edge("generate_quiz", "validate_quiz")
    graph.add_conditional_edges(
        "validate_quiz",
        _route_after_validate_quiz,
        {
            "generate_quiz": "generate_quiz",
            "generate_pbl": "generate_pbl",
            "merge_results": "merge_results",
        },
    )
    graph.add_edge("generate_pbl", "validate_pbl")
    graph.add_conditional_edges(
        "validate_pbl",
        _route_after_validate_pbl,
        {
            "generate_pbl": "generate_pbl",
            "merge_results": "merge_results",
        },
    )
    graph.add_edge("merge_results", END)

    return graph.compile()


_COMPILED_GRAPH: ContentGenerationGraph | None = None


def _get_compiled_graph() -> ContentGenerationGraph:
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_content_generation_graph()
    return _COMPILED_GRAPH


def reset_content_generation_graph_cache() -> None:
    """Clear the memoized compiled graph (for tests)."""
    global _COMPILED_GRAPH
    _COMPILED_GRAPH = None


def initial_content_generation_state(
    topic: str,
    *,
    grade_level: str = "6th grade",
) -> ContentGenerationState:
    """Build the initial graph state for content generation."""
    return ContentGenerationState(
        topic=topic,
        grade_level=grade_level,
        lesson_retry_count=0,
        quiz_retry_count=0,
        pbl_retry_count=0,
        generation_complete=False,
    )


async def run_content_generation_graph(
    topic: str,
    *,
    grade_level: str = "6th grade",
    config: RunnableConfig | None = None,
) -> ContentGenerationState:
    """Run the content-generation graph with workflow timeout enforcement."""
    from mcp_server.application.agent import ainvoke_with_workflow_timeout

    graph = _get_compiled_graph()
    state = initial_content_generation_state(topic, grade_level=grade_level)
    result = await ainvoke_with_workflow_timeout(graph, state, config=config)
    return cast(ContentGenerationState, result)


def get_content_generation_graph() -> ContentGenerationGraph:
    """Return the memoized content-generation graph for workflow registration."""
    return _get_compiled_graph()
