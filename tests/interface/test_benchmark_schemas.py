"""Tests for local benchmark API schemas."""

import pytest
from pydantic import ValidationError

from mcp_server.interface.local_ui.benchmark_schemas import (
    BenchmarkCompleteEventView,
    BenchmarkProgressEventView,
    RagOptimizationRequest,
)


def test_benchmark_progress_event_view_rejects_out_of_range_progress() -> None:
    with pytest.raises(ValidationError):
        BenchmarkProgressEventView(
            stage="indexing",
            progress=101,
            message="Indexing",
        )


def test_benchmark_complete_event_view_requires_result() -> None:
    with pytest.raises(ValidationError):
        BenchmarkCompleteEventView(
            stage="complete",
            progress=100,
            message="Benchmark complete",
        )


def test_rag_optimization_request_rejects_invalid_max_scenarios() -> None:
    with pytest.raises(ValidationError):
        RagOptimizationRequest(max_scenarios=0)
