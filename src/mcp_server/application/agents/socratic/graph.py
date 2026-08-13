"""Compile and run the socratic-tutor LangGraph workflow (E8)."""

from __future__ import annotations

from typing import Literal, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from mcp_server.application.agents.socratic.nodes import (
    generate_reply,
    ground_context,
    validate_reply,
)
from mcp_server.application.agents.socratic.state import SocraticTutorState
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)
from mcp_server.application.workflow_trace import invoke_graph_with_trace
from mcp_server.domain.socratic import (
    SocraticMessage,
    SocraticReply,
    normalize_locale,
)

SocraticTutorGraph = CompiledStateGraph[
    SocraticTutorState, SocraticTutorState, SocraticTutorState
]

_graph: SocraticTutorGraph | None = None


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def _route_after_validate(
    state: SocraticTutorState,
) -> Literal["generate_reply"] | object:
    errors = state.get("validation_errors") or []
    retries = int(state.get("reply_retry_count") or 0)
    if errors and retries < 1 and state.get("reply"):
        return "generate_reply"
    return END


def build_socratic_tutor_graph() -> SocraticTutorGraph:
    graph: StateGraph[SocraticTutorState, SocraticTutorState, SocraticTutorState] = StateGraph(
        SocraticTutorState
    )
    config = _workflow_runtime_config()
    retry = RetryPolicy(max_attempts=max(config.node_retries + 1, 1))
    timeout = config.agent_node_timeout_seconds

    graph.add_node("ground_context", ground_context, timeout=timeout)
    graph.add_node("generate_reply", generate_reply, retry_policy=retry, timeout=timeout)
    graph.add_node("validate_reply", validate_reply, timeout=timeout)

    graph.add_edge(START, "ground_context")
    graph.add_edge("ground_context", "generate_reply")
    graph.add_edge("generate_reply", "validate_reply")
    graph.add_conditional_edges("validate_reply", _route_after_validate)
    return cast(SocraticTutorGraph, graph.compile())


def get_socratic_tutor_graph() -> SocraticTutorGraph:
    global _graph
    if _graph is None:
        _graph = build_socratic_tutor_graph()
    return _graph


def reset_socratic_tutor_graph_cache() -> None:
    global _graph
    _graph = None


def initial_socratic_tutor_state(
    *,
    tenant_id: str,
    course_slug: str,
    message: str,
    module_slug: str | None = None,
    lesson_slug: str | None = None,
    project_slug: str | None = None,
    history: list[SocraticMessage] | None = None,
    hint_level: int = 1,
    locale: str = "en",
    want_full_solution: bool = False,
) -> SocraticTutorState:
    return {
        "tenant_id": tenant_id,
        "course_slug": course_slug,
        "module_slug": module_slug,
        "lesson_slug": lesson_slug,
        "project_slug": project_slug,
        "message": message,
        "history": list(history or []),
        "hint_level": max(1, min(5, int(hint_level))),
        "locale": normalize_locale(locale),
        "want_full_solution": want_full_solution,
        "grounding": None,
        "reply": None,
        "validation_errors": [],
        "reply_retry_count": 0,
        "result": None,
        "error": None,
        "model_id": None,
        "llm_io": [],
    }


async def run_socratic_tutor_graph(**kwargs: object) -> tuple[SocraticTutorState, object]:
    from mcp_server.application.agent import workflow_timeout_seconds

    graph = get_socratic_tutor_graph()
    history_raw = kwargs.get("history") or []
    history: list[SocraticMessage] = []
    if isinstance(history_raw, list):
        for item in history_raw:
            if isinstance(item, SocraticMessage):
                history.append(item)
            elif isinstance(item, dict):
                history.append(SocraticMessage.model_validate(item))

    state = initial_socratic_tutor_state(
        tenant_id=str(kwargs["tenant_id"]),
        course_slug=str(kwargs["course_slug"]),
        message=str(kwargs["message"]),
        module_slug=str(kwargs["module_slug"]) if kwargs.get("module_slug") else None,
        lesson_slug=str(kwargs["lesson_slug"]) if kwargs.get("lesson_slug") else None,
        project_slug=str(kwargs["project_slug"]) if kwargs.get("project_slug") else None,
        history=history,
        hint_level=int(kwargs.get("hint_level") or 1),
        locale=str(kwargs.get("locale") or "en"),
        want_full_solution=bool(kwargs.get("want_full_solution", False)),
    )
    return await invoke_graph_with_trace(
        graph,
        state,
        timeout_seconds=workflow_timeout_seconds(),
    )


def result_from_state(state: SocraticTutorState) -> SocraticReply:
    result = state.get("result")
    if result is not None:
        return result
    reply = str(state.get("reply") or state.get("error") or "Tutor could not respond.")
    return SocraticReply(
        reply=reply[:2000],
        hint_level=int(state.get("hint_level") or 1),
        locale=normalize_locale(state.get("locale")),
        asked_full_solution=bool(state.get("want_full_solution")),
        grounding_used=False,
    )
