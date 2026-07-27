"""Benchmark orchestration with streamed progress events."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Literal

from mcp_server.application.agents.rag_validation.fixture import save_optimized_hyperparameters
from mcp_server.application.agents.rag_validation.graph import (
    get_rag_validation_graph,
    initial_rag_validation_state,
    rag_validation_workflow_timeout_seconds,
    run_rag_validation_graph,
)
from mcp_server.application.agents.rag_validation.optimization_report import (
    build_report_from_optimization,
    config_score_to_phase_result,
    default_baseline_hyperparameters,
    save_optimization_report,
)
from mcp_server.application.agents.rag_validation.optimizer import (
    RagHyperparameterOptimizer,
    default_rag_hyperparameter_search_space,
)
from mcp_server.application.agents.rag_validation.scenarios import RagSearchScenario
from mcp_server.application.agents.rag_validation.test_dataset_loader import (
    DEFAULT_MAX_SCENARIOS,
    load_test_dataset_scenarios,
)
from mcp_server.application.workflow_trace import (
    GraphStreamComplete,
    WorkflowTraceStep,
    stream_graph_with_trace,
)
from mcp_server.domain.rag_hyperparameters import RagHyperparameters, score_config_results

BenchmarkStage = Literal["indexing", "embedding", "retrieving", "validating", "complete", "error"]
OptimizationStage = Literal["baseline", "searching", "saving", "after", "complete", "error"]

_RAG_NODE_PROGRESS: dict[str, tuple[BenchmarkStage, int, str]] = {
    "load_document": ("indexing", 10, "Loading document"),
    "index_document": ("indexing", 30, "Indexing document chunks"),
    "embed_query": ("embedding", 45, "Embedding query"),
    "retrieve_chunks": ("retrieving", 60, "Retrieving chunks"),
    "rerank_chunks": ("retrieving", 75, "Reranking chunks"),
    "merge_context": ("validating", 85, "Merging retrieval context"),
    "validate_retrieval": ("validating", 95, "Validating phrase coverage"),
}


@dataclass(frozen=True, slots=True)
class BenchmarkSummary:
    """Catalog entry for a runnable benchmark."""

    id: str
    name: str
    description: str
    workflow_id: str


@dataclass(frozen=True, slots=True)
class BenchmarkProgressEvent:
    """Progress update emitted while a benchmark executes."""

    stage: BenchmarkStage
    progress: int
    message: str
    step: int | None = None
    total: int | None = None
    node_id: str | None = None
    scenario_id: str | None = None
    scenario_index: int | None = None
    scenario_total: int | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkCompleteEvent:
    """Final benchmark payload with graph state and trace."""

    stage: Literal["complete"]
    progress: int
    message: str
    state: Any
    trace: list[WorkflowTraceStep]
    dataset_report: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkErrorEvent:
    """Terminal error for a benchmark run."""

    stage: Literal["error"]
    progress: int
    message: str


BenchmarkStreamEvent = BenchmarkProgressEvent | BenchmarkCompleteEvent | BenchmarkErrorEvent


@dataclass(frozen=True, slots=True)
class RagOptimizationProgressEvent:
    """Progress update emitted while hyperparameter optimization runs."""

    stage: OptimizationStage
    progress: int
    message: str
    scenario_count: int | None = None
    combination_index: int | None = None
    combination_total: int | None = None


@dataclass(frozen=True, slots=True)
class RagOptimizationCompleteEvent:
    """Terminal optimization payload with before/after report."""

    stage: Literal["complete"]
    progress: int
    message: str
    report: dict[str, Any]
    optimized_hyperparameters: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RagOptimizationErrorEvent:
    """Terminal optimization failure."""

    stage: Literal["error"]
    progress: int
    message: str


RagOptimizationStreamEvent = (
    RagOptimizationProgressEvent | RagOptimizationCompleteEvent | RagOptimizationErrorEvent
)

_REGISTERED_BENCHMARKS: tuple[BenchmarkSummary, ...] = (
    BenchmarkSummary(
        id="rag",
        name="RAG Test-Dataset Benchmark",
        description=(
            "Runs rag-validation against eval scenarios from test-dataset/ "
            "(one indexed document and query per scenario) and reports aggregate phrase coverage."
        ),
        workflow_id="rag-validation",
    ),
)


def list_benchmarks() -> list[BenchmarkSummary]:
    """Return registered benchmark catalog entries."""
    return list(_REGISTERED_BENCHMARKS)


def get_benchmark(benchmark_id: str) -> BenchmarkSummary | None:
    """Look up a benchmark by id."""
    return next((item for item in _REGISTERED_BENCHMARKS if item.id == benchmark_id), None)


def _progress_for_node(node_id: str, step_index: int) -> BenchmarkProgressEvent:
    stage, progress, message = _RAG_NODE_PROGRESS.get(
        node_id,
        ("validating", min(95, 10 + step_index * 8), f"Running {node_id}"),
    )
    return BenchmarkProgressEvent(
        stage=stage,
        progress=progress,
        message=message,
        step=step_index,
        total=len(_RAG_NODE_PROGRESS),
        node_id=node_id,
    )


async def stream_rag_dataset_benchmark(
    *,
    hyperparameters: RagHyperparameters,
    max_scenarios: int = DEFAULT_MAX_SCENARIOS,
    scenarios: list[RagSearchScenario] | None = None,
) -> AsyncIterator[BenchmarkStreamEvent]:
    """Run rag-validation once per test-dataset scenario and aggregate benchmarks."""
    try:
        loaded_scenarios = scenarios or load_test_dataset_scenarios(max_scenarios=max_scenarios)
        if not loaded_scenarios:
            yield BenchmarkErrorEvent(
                stage="error",
                progress=0,
                message="No eval scenarios available in the test dataset.",
            )
            return

        scenario_total = len(loaded_scenarios)
        scenario_lookup = {scenario.name: scenario.query for scenario in loaded_scenarios}
        optimizer = RagHyperparameterOptimizer(
            search_space=default_rag_hyperparameter_search_space(),
            scenarios=loaded_scenarios,
            run_validation=run_rag_validation_graph,
        )

        last_result = None
        scenario_results = []
        for scenario_index, scenario in enumerate(loaded_scenarios, start=1):
            progress = int(((scenario_index - 1) / scenario_total) * 90)
            yield BenchmarkProgressEvent(
                stage="indexing",
                progress=progress,
                message=(
                    f"Scenario {scenario.name} ({scenario_index}/{scenario_total}): "
                    f"{scenario.query[:80]}{'…' if len(scenario.query) > 80 else ''}"
                ),
                step=scenario_index,
                total=scenario_total,
                scenario_id=scenario.name,
                scenario_index=scenario_index,
                scenario_total=scenario_total,
            )
            result = await optimizer.evaluate_scenario(hyperparameters, scenario)
            scenario_results.append(result)
            last_result = result

        score = score_config_results(hyperparameters, scenario_results)
        phase = config_score_to_phase_result(score, scenario_lookup=scenario_lookup)
        dataset_report = phase.as_dict()
        dataset_report["scenario_count"] = scenario_total

        yield BenchmarkProgressEvent(
            stage="validating",
            progress=95,
            message=(
                f"Aggregated {scenario_total} scenario(s): "
                f"mean semantic relevance {score.mean_gold_semantic_relevance:.1%}"
                if score.mean_gold_semantic_relevance > 0.0
                else f"mean phrase coverage {score.mean_phrase_coverage:.1%}"
            ),
            scenario_total=scenario_total,
        )

        synthetic_state = _synthetic_state_from_score(last_result, score, hyperparameters)
        yield BenchmarkCompleteEvent(
            stage="complete",
            progress=100,
            message=f"Benchmark complete across {scenario_total} test-dataset scenario(s)",
            state=synthetic_state,
            trace=[],
            dataset_report=dataset_report,
        )
    except Exception as exc:
        yield BenchmarkErrorEvent(
            stage="error",
            progress=0,
            message=str(exc),
        )


def _synthetic_state_from_score(
    last_scenario_result: Any,
    score: Any,
    hyperparameters: RagHyperparameters,
) -> dict[str, Any]:
    """Build a minimal validation state for the UI aggregate dashboard."""
    last_benchmarks = (
        last_scenario_result.benchmarks.as_dict()
        if last_scenario_result is not None and hasattr(last_scenario_result, "benchmarks")
        else {}
    )
    return {
        "query": "test-dataset aggregate",
        "retrieval_mode": hyperparameters.retrieval_mode,
        "retrieve_limit": hyperparameters.retrieve_limit,
        "rerank_enabled": hyperparameters.rerank_enabled,
        "rerank_top_n": hyperparameters.rerank_top_n,
        "retrieval_complete": True,
        "index_complete": True,
        "validation_passed": score.validation_pass_rate >= 1.0,
        "validation_errors": [],
        "document_title": "test-dataset (aggregate)",
        "document_source": "test-dataset",
        "indexed_chunk_count": 0,
        "rag_benchmarks": {
            "phrase_coverage": score.mean_phrase_coverage,
            "phrase_chunk_rate": score.mean_phrase_coverage,
            "any_phrase_hit": score.mean_phrase_coverage,
            "first_phrase_rank_reciprocal": score.mean_first_phrase_rank_reciprocal,
            "gold_semantic_relevance": score.mean_gold_semantic_relevance,
            "mean_gold_semantic_relevance": score.mean_gold_semantic_relevance,
            "gold_semantic_precision": score.mean_gold_semantic_precision,
            "gold_semantic_rank_reciprocal": score.mean_first_phrase_rank_reciprocal,
            "expected_phrase_count": len(score.scenario_results),
            "matched_phrase_count": sum(
                1 for result in score.scenario_results if result.validation_passed
            ),
            "retrieved_chunk_count": hyperparameters.retrieve_limit,
            **last_benchmarks,
        },
        "rag_evaluation_context": {
            "retrieval_mode": hyperparameters.retrieval_mode,
            "retrieve_limit": hyperparameters.retrieve_limit,
            "rerank_enabled": hyperparameters.rerank_enabled,
            "rerank_top_n": hyperparameters.rerank_top_n,
            "effective_k": hyperparameters.retrieve_limit,
            "score_kind": "cosine",
        },
    }


async def stream_rag_benchmark(
    *,
    query: str | None = None,
    fixture_path: str | None = None,
    document_text: str | None = None,
    document_title: str | None = None,
    expected_phrases: list[str] | None = None,
    retrieval_mode: str = "vector",
    retrieve_limit: int = 10,
    rerank_top_n: int = 6,
    rerank_enabled: bool = False,
    course_id: str | None = None,
    tags: list[str] | None = None,
    language: str | None = "en",
) -> AsyncIterator[BenchmarkStreamEvent]:
    """Run the RAG validation benchmark and yield progress + final result events."""
    graph = get_rag_validation_graph()
    state = initial_rag_validation_state(
        query,
        fixture_path=fixture_path,
        document_text=document_text,
        document_title=document_title,
        expected_phrases=expected_phrases,
        retrieval_mode=retrieval_mode,
        retrieve_limit=retrieve_limit,
        rerank_top_n=rerank_top_n,
        rerank_enabled=rerank_enabled,
        course_id=course_id,
        tags=tags,
        language=language,
    )

    step_index = 0
    try:
        async for item in stream_graph_with_trace(
            graph,
            state,
            timeout_seconds=rag_validation_workflow_timeout_seconds(),
        ):
            if isinstance(item, WorkflowTraceStep):
                step_index += 1
                yield _progress_for_node(item.node_id, step_index)
                continue

            if isinstance(item, GraphStreamComplete):
                yield BenchmarkCompleteEvent(
                    stage="complete",
                    progress=100,
                    message="Benchmark complete",
                    state=item.state,
                    trace=item.trace,
                )
    except TimeoutError:
        yield BenchmarkErrorEvent(
            stage="error",
            progress=min(99, step_index * 12),
            message="Benchmark execution timed out.",
        )
    except Exception as exc:
        yield BenchmarkErrorEvent(
            stage="error",
            progress=min(99, step_index * 12),
            message=str(exc),
        )


async def stream_benchmark(
    benchmark_id: str,
    *,
    hyperparameters: RagHyperparameters | None = None,
    max_scenarios: int = DEFAULT_MAX_SCENARIOS,
    query: str | None = None,
    fixture_path: str | None = None,
    document_text: str | None = None,
    document_title: str | None = None,
    expected_phrases: list[str] | None = None,
    retrieval_mode: str = "vector",
    retrieve_limit: int = 10,
    rerank_top_n: int = 6,
    rerank_enabled: bool = False,
    course_id: str | None = None,
    tags: list[str] | None = None,
    language: str | None = "en",
) -> AsyncIterator[BenchmarkStreamEvent]:
    """Dispatch a benchmark run by id."""
    benchmark = get_benchmark(benchmark_id)
    if benchmark is None:
        yield BenchmarkErrorEvent(
            stage="error",
            progress=0,
            message=f"Benchmark '{benchmark_id}' not found.",
        )
        return

    if benchmark_id == "rag":
        params = hyperparameters or RagHyperparameters(
            retrieval_mode="hybrid" if retrieval_mode == "hybrid" else "vector",
            retrieve_limit=retrieve_limit,
            rerank_enabled=rerank_enabled,
            rerank_top_n=rerank_top_n,
        )
        async for event in stream_rag_dataset_benchmark(
            hyperparameters=params,
            max_scenarios=max_scenarios,
        ):
            yield event
        return

    yield BenchmarkErrorEvent(
        stage="error",
        progress=0,
        message=f"Benchmark '{benchmark_id}' is not implemented.",
    )


async def stream_rag_optimization(
    *,
    max_scenarios: int = DEFAULT_MAX_SCENARIOS,
    max_combinations: int | None = None,
    baseline: RagHyperparameters | None = None,
    scenarios: list[RagSearchScenario] | None = None,
    optimizer_factory: (
        Callable[[list[RagSearchScenario]], RagHyperparameterOptimizer] | None
    ) = None,
) -> AsyncIterator[RagOptimizationStreamEvent]:
    """Run baseline → grid search → after benchmarks with streamed progress."""
    try:
        loaded_scenarios = scenarios or load_test_dataset_scenarios(max_scenarios=max_scenarios)
        if not loaded_scenarios:
            yield RagOptimizationErrorEvent(
                stage="error",
                progress=0,
                message="No eval scenarios available in the test dataset.",
            )
            return

        scenario_count = len(loaded_scenarios)
        scenario_lookup = {scenario.name: scenario.query for scenario in loaded_scenarios}
        search_space = default_rag_hyperparameter_search_space()
        optimizer = (
            optimizer_factory(loaded_scenarios)
            if optimizer_factory is not None
            else RagHyperparameterOptimizer(
                search_space=search_space,
                scenarios=loaded_scenarios,
            )
        )
        combinations = optimizer.plan_combinations(max_combinations=max_combinations)
        baseline_params = baseline or default_baseline_hyperparameters()

        yield RagOptimizationProgressEvent(
            stage="baseline",
            progress=5,
            message=f"Running baseline benchmarks across {scenario_count} scenario(s)…",
            scenario_count=scenario_count,
        )
        before_score = await optimizer.evaluate_hyperparameters(baseline_params)

        combination_total = len(combinations)
        yield RagOptimizationProgressEvent(
            stage="searching",
            progress=20,
            message=(
                f"Searching {combination_total} hyperparameter combination(s) "
                f"across {scenario_count} scenario(s)…"
            ),
            scenario_count=scenario_count,
            combination_total=combination_total,
        )
        config_scores = []
        async for index, total, score in optimizer.evaluate_combinations(
            max_combinations=max_combinations,
        ):
            config_scores.append(score)
            search_progress = 20 + int((index / total) * 50)
            yield RagOptimizationProgressEvent(
                stage="searching",
                progress=search_progress,
                message=(
                    f"Evaluating hyperparameter combination {index} of {total} "
                    f"across {scenario_count} scenario(s)…"
                ),
                scenario_count=scenario_count,
                combination_index=index,
                combination_total=total,
            )
        optimized = optimizer.finalize_from_scores(config_scores)

        yield RagOptimizationProgressEvent(
            stage="saving",
            progress=75,
            message="Saving optimized hyperparameters…",
            scenario_count=scenario_count,
        )
        save_optimized_hyperparameters(optimized)

        yield RagOptimizationProgressEvent(
            stage="after",
            progress=85,
            message="Running after benchmarks with optimized hyperparameters…",
            scenario_count=scenario_count,
        )
        after_score = await optimizer.evaluate_hyperparameters(optimized.hyperparameters)
        report = build_report_from_optimization(
            before_score=before_score,
            optimized=optimized,
            after_score=after_score,
            scenario_lookup=scenario_lookup,
        )
        save_optimization_report(report)

        yield RagOptimizationCompleteEvent(
            stage="complete",
            progress=100,
            message="Hyperparameter optimization complete",
            report=report.as_dict(),
            optimized_hyperparameters=optimized.hyperparameters.as_dict(),
        )
    except Exception as exc:
        yield RagOptimizationErrorEvent(
            stage="error",
            progress=0,
            message=str(exc),
        )
