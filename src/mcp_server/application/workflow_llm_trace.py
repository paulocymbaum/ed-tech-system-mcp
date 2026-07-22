"""Capture LLM prompts and raw output for workflow UI traces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_pending_llm_io: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class LlmTraceRecord:
    """Prompts and raw model text for one generation node invocation."""

    system_prompt: str
    user_prompt: str
    raw_output: str


def reset_llm_trace_capture() -> None:
    """Clear pending LLM trace data (call at the start of each traced run)."""
    global _pending_llm_io
    _pending_llm_io = None


def record_llm_invocation(
    *,
    system_prompt: str,
    user_prompt: str,
    raw_output: str,
) -> None:
    """Store LLM I/O for attachment to the next workflow trace step."""
    global _pending_llm_io
    _pending_llm_io = {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "raw_output": raw_output,
    }


def consume_llm_trace() -> dict[str, Any] | None:
    """Return and clear the pending LLM trace payload."""
    global _pending_llm_io
    payload = _pending_llm_io
    _pending_llm_io = None
    return payload
