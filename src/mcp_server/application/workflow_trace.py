"""Collect per-node execution traces from LangGraph streaming runs."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.graph.state import CompiledStateGraph

from mcp_server.application.workflow_llm_trace import consume_llm_trace, reset_llm_trace_capture

TraceStepStatus = Literal["ok", "failed", "retry"]


@dataclass(frozen=True, slots=True)
class WorkflowTraceStep:
    """One executed graph node update captured from ``stream_mode='updates'``."""

    step: int
    node_id: str
    status: TraceStepStatus
    attempt: int
    validation_errors: tuple[str, ...] = ()
    retry_counts: dict[str, int] = field(default_factory=dict)
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    output_update: dict[str, Any] = field(default_factory=dict)
    llm_io: dict[str, Any] | None = None


_RETRY_COUNT_KEYS = (
    "lesson_retry_count",
    "quiz_retry_count",
    "pbl_retry_count",
)

_VALIDATION_ERROR_KEYS = (
    "lesson_validation_errors",
    "quiz_validation_errors",
    "pbl_validation_errors",
)


def serialize_trace_value(value: Any) -> Any:
    """Convert graph state values into JSON-serializable trace payloads."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): serialize_trace_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_trace_value(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_trace_value(item) for item in value]
    return value


def _validation_errors(update: dict[str, Any] | None) -> list[str]:
    if not update:
        return []
    for key in _VALIDATION_ERROR_KEYS:
        raw = update.get(key)
        if isinstance(raw, list) and raw:
            return [str(item) for item in raw]
    return []


def _retry_counts(update: dict[str, Any] | None) -> dict[str, int]:
    if not update:
        return {}
    counts: dict[str, int] = {}
    for key in _RETRY_COUNT_KEYS:
        raw = update.get(key)
        if isinstance(raw, int):
            counts[key] = raw
    return counts


def _step_status(node_id: str, update: dict[str, Any] | None) -> TraceStepStatus:
    errors = _validation_errors(update)
    if errors:
        return "failed"
    if node_id.startswith("validate_") and _retry_counts(update):
        return "retry"
    return "ok"


async def invoke_graph_with_trace(
    graph: CompiledStateGraph[Any, Any, Any],
    state: Any,
    *,
    timeout_seconds: float,
) -> tuple[Any, list[WorkflowTraceStep]]:
    """Run a compiled graph and return the merged final state plus a replayable trace."""
    running_state = dict(state)
    steps: list[WorkflowTraceStep] = []
    attempts: dict[str, int] = defaultdict(int)
    reset_llm_trace_capture()

    async def _stream() -> None:
        nonlocal running_state
        step_index = 0
        async for chunk in graph.astream(state, stream_mode="updates"):
            step_index += 1
            node_id, raw_update = next(iter(chunk.items()))
            update = raw_update if isinstance(raw_update, dict) else None
            attempts[node_id] += 1
            input_snapshot = serialize_trace_value(dict(running_state))
            llm_io = consume_llm_trace()
            if llm_io is not None:
                input_snapshot = {
                    **input_snapshot,
                    "llm_request": {
                        "model_name": llm_io.get("model_name"),
                        "llm_complexity": llm_io.get("llm_complexity"),
                        "input_tokens": llm_io.get("input_tokens"),
                        "output_tokens": llm_io.get("output_tokens"),
                        "total_tokens": llm_io.get("total_tokens"),
                    },
                }
            if update:
                running_state.update(update)
            output_update = serialize_trace_value(update or {})
            if llm_io is not None:
                output_update = {
                    **output_update,
                    "model_name": llm_io.get("model_name"),
                    "llm_complexity": llm_io.get("llm_complexity"),
                    "input_tokens": llm_io.get("input_tokens"),
                    "output_tokens": llm_io.get("output_tokens"),
                    "total_tokens": llm_io.get("total_tokens"),
                }
            steps.append(
                WorkflowTraceStep(
                    step=step_index,
                    node_id=node_id,
                    status=_step_status(node_id, update),
                    attempt=attempts[node_id],
                    validation_errors=tuple(_validation_errors(update)),
                    retry_counts=_retry_counts(update),
                    input_snapshot=input_snapshot,
                    output_update=output_update,
                    llm_io=llm_io,
                )
            )

    await asyncio.wait_for(_stream(), timeout=timeout_seconds)
    return running_state, steps
