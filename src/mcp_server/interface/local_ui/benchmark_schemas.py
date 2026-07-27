"""API schemas for local benchmark streaming."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from mcp_server.interface.validation import RagValidationRunResponse

BenchmarkStage = Literal["indexing", "embedding", "retrieving", "validating", "complete", "error"]
OptimizationStage = Literal["baseline", "searching", "saving", "after", "complete", "error"]


class BenchmarkSummaryView(BaseModel):
    """Catalog entry exposed to the local UI."""

    id: str
    name: str
    description: str
    workflow_id: str


class BenchmarkProgressEventView(BaseModel):
    """Incremental progress event streamed during benchmark execution."""

    stage: BenchmarkStage
    progress: int = Field(ge=0, le=100)
    message: str
    step: int | None = None
    total: int | None = None
    node_id: str | None = None
    scenario_id: str | None = None
    scenario_index: int | None = None
    scenario_total: int | None = None


class RagBenchmarkRunRequest(BaseModel):
    """Request body for POST /api/benchmarks/rag/run (test-dataset scenarios)."""

    max_scenarios: int = Field(default=12, ge=1)
    retrieval_mode: Literal["vector", "hybrid"] = "vector"
    retrieve_limit: int = Field(default=4, ge=1, le=100)
    rerank_top_n: int = Field(default=4, ge=1, le=50)
    rerank_enabled: bool = False


class BenchmarkCompleteEventView(BenchmarkProgressEventView):
    """Terminal success event including the workflow run payload."""

    stage: Literal["complete"] = "complete"
    progress: int = 100
    result: RagValidationRunResponse
    dataset_report: dict[str, Any] | None = None


class BenchmarkErrorEventView(BenchmarkProgressEventView):
    """Terminal failure event."""

    stage: Literal["error"] = "error"


class RagOptimizationRequest(BaseModel):
    """Request body for POST /api/benchmarks/rag/optimize."""

    max_scenarios: int = Field(default=12, ge=1)
    max_combinations: int | None = Field(default=None, ge=1)
    retrieval_mode: Literal["vector", "hybrid"] = "vector"
    retrieve_limit: int = Field(default=4, ge=1, le=100)
    rerank_top_n: int = Field(default=4, ge=1, le=50)
    rerank_enabled: bool = False


class RagOptimizationProgressEventView(BaseModel):
    """Incremental progress event streamed during hyperparameter optimization."""

    stage: OptimizationStage
    progress: int = Field(ge=0, le=100)
    message: str
    scenario_count: int | None = None
    combination_index: int | None = None
    combination_total: int | None = None


class RagOptimizationCompleteEventView(RagOptimizationProgressEventView):
    """Terminal optimization success event with before/after report."""

    stage: Literal["complete"] = "complete"
    progress: int = 100
    report: dict[str, Any]
    optimized_hyperparameters: dict[str, Any]


class RagOptimizationErrorEventView(RagOptimizationProgressEventView):
    """Terminal optimization failure event."""

    stage: Literal["error"] = "error"


class TestDatasetSummaryView(BaseModel):
    """Scenario counts from the bundled test dataset."""

    total_scenarios: int
    eval_scenarios: int
    answer_in_corpus_scenarios: int
    default_max_scenarios: int
    scenario_ids: list[str]


class RagOptimizationReportView(BaseModel):
    """Persisted before/after optimization report."""

    created_at: str
    scenario_count: int
    before: dict[str, Any]
    after: dict[str, Any]
    diff: dict[str, float]
    optimized_at: str
    objective: str
