"""Tests for tiktoken-backed token counting."""

from __future__ import annotations

from mcp_server.application.token_counting_runtime import reset_token_counter, set_token_counter
from mcp_server.application.workflow_llm_trace import (
    consume_llm_trace,
    record_llm_invocation,
    reset_llm_trace_capture,
)
from mcp_server.infrastructure.token_counting.tiktoken_counter import (
    TiktokenTokenCounter,
    resolve_encoding_name,
)


def setup_function() -> None:
    reset_llm_trace_capture()
    reset_token_counter()
    set_token_counter(TiktokenTokenCounter())


def teardown_function() -> None:
    reset_token_counter()


def test_resolve_encoding_name_defaults_to_cl100k_for_llama() -> None:
    assert resolve_encoding_name("llama-3.3-70b-versatile") == "cl100k_base"


def test_resolve_encoding_name_unknown_and_none_default_cl100k() -> None:
    assert resolve_encoding_name(None) == "cl100k_base"
    assert resolve_encoding_name("unknown-model-x") == "cl100k_base"


def test_tiktoken_counter_counts_non_empty_text() -> None:
    counter = TiktokenTokenCounter()
    assert counter.count("hello world") > 0
    assert counter.count("") == 0


def test_record_llm_invocation_includes_token_fields() -> None:
    record_llm_invocation(
        system_prompt="You are helpful.",
        user_prompt="Say hello.",
        raw_output="Hello!",
        model_name="llama-3.3-70b-versatile",
        llm_complexity=2,
    )
    payload = consume_llm_trace()
    assert payload is not None
    assert payload["input_tokens"] > 0
    assert payload["output_tokens"] > 0
    assert payload["total_tokens"] == payload["input_tokens"] + payload["output_tokens"]
    assert payload["token_breakdown"]["system_prompt_tokens"] > 0
    assert payload["token_breakdown"]["user_prompt_tokens"] > 0
    assert payload["token_breakdown"]["raw_output_tokens"] > 0


def test_noop_token_counter_returns_zero_counts() -> None:
    reset_token_counter()
    record_llm_invocation(
        system_prompt="You are helpful.",
        user_prompt="Say hello.",
        raw_output="Hello!",
        model_name="llama-3.3-70b-versatile",
        llm_complexity=2,
    )
    payload = consume_llm_trace()
    assert payload is not None
    assert payload["input_tokens"] == 0
    assert payload["output_tokens"] == 0
    assert payload["total_tokens"] == 0
    assert payload["token_breakdown"]["system_prompt_tokens"] == 0
    assert payload["token_breakdown"]["user_prompt_tokens"] == 0
    assert payload["token_breakdown"]["raw_output_tokens"] == 0
