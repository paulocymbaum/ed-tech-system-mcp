"""Capture LLM prompts and raw output for workflow UI traces."""

from __future__ import annotations

from typing import Any

from mcp_server.application.token_counting_runtime import get_token_counter

_pending_llm_io: dict[str, Any] | None = None


def reset_llm_trace_capture() -> None:
    """Clear pending LLM trace data (call at the start of each traced run)."""
    global _pending_llm_io
    _pending_llm_io = None


def record_llm_invocation(
    *,
    system_prompt: str,
    user_prompt: str,
    raw_output: str,
    model_name: str,
    llm_complexity: int,
) -> None:
    """Store LLM I/O for attachment to the next workflow trace step."""
    global _pending_llm_io
    token_counts = get_token_counter().count_invocation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_output=raw_output,
        model_name=model_name,
    )
    _pending_llm_io = {
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
    """Return and clear the pending LLM trace payload."""
    global _pending_llm_io
    payload = _pending_llm_io
    _pending_llm_io = None
    return payload
