"""Capture LLM prompts and raw output for workflow UI traces."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from mcp_server.application.token_counting_runtime import get_token_counter

_trace_run_id: ContextVar[str | None] = ContextVar("llm_trace_run_id", default=None)
_pending_by_run: dict[str, dict[str, Any]] = {}


def reset_llm_trace_capture() -> None:
    """Start a traced run; later records attach to this run id."""
    previous = _trace_run_id.get()
    if previous is not None:
        _pending_by_run.pop(previous, None)
    run_id = uuid4().hex
    _trace_run_id.set(run_id)
    _pending_by_run.pop(run_id, None)


def record_llm_invocation(
    *,
    system_prompt: str,
    user_prompt: str,
    raw_output: str,
    model_name: str,
    llm_complexity: int,
) -> None:
    """Store LLM I/O for attachment to the next workflow trace step."""
    run_id = _trace_run_id.get()
    if run_id is None:
        return
    token_counts = get_token_counter().count_invocation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_output=raw_output,
        model_name=model_name,
    )
    _pending_by_run[run_id] = {
        "model_name": model_name,
        "llm_complexity": llm_complexity,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_output": raw_output,
        "input_tokens": token_counts.input_tokens,
        "output_tokens": token_counts.output_tokens,
        "total_tokens": token_counts.total_tokens,
        "token_breakdown": {
            "system_prompt_tokens": token_counts.system_prompt_tokens,
            "user_prompt_tokens": token_counts.user_prompt_tokens,
            "raw_output_tokens": token_counts.raw_output_tokens,
        },
    }


def consume_llm_trace() -> dict[str, Any] | None:
    """Return and clear the pending LLM trace payload for this run."""
    run_id = _trace_run_id.get()
    if run_id is None:
        return None
    return _pending_by_run.pop(run_id, None)
