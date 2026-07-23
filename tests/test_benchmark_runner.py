"""Tests for benchmark orchestration and streamed progress events."""

from __future__ import annotations

import pytest

from mcp_server.application.agents.rag_validation.scenarios import RagSearchScenario
from mcp_server.application.benchmark_runner import (
    _RAG_NODE_PROGRESS,
    BenchmarkCompleteEvent,
    BenchmarkErrorEvent,
    BenchmarkProgressEvent,
    RagOptimizationCompleteEvent,
    RagOptimizationErrorEvent,
    RagOptimizationProgressEvent,
    get_benchmark,
    list_benchmarks,
    stream_benchmark,
    stream_rag_benchmark,
    stream_rag_dataset_benchmark,
    stream_rag_optimization,
)
from mcp_server.application.retrieval_runtime import (
    reset_retrieval_clients,
    set_chunking_strategy,
    set_embedding_provider,
    set_reranker,
    set_vector_index_writer,
    set_vector_retriever,
)
from mcp_server.application.token_counting_runtime import set_token_counter
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.domain.rag_hyperparameters import (
    OBJECTIVE_MEAN_PHRASE_COVERAGE,
    OptimizedRagHyperparameters,
    RagHyperparameters,
    RagHyperparameterSearchSpace,
)
from mcp_server.infrastructure.rerank.noop_reranker import NoOpReranker
from mcp_server.infrastructure.token_counting.tiktoken_counter import TiktokenTokenCounter
from rag_fakes import (
    FakeChunkingStrategy,
    FakeEmbeddingProvider,
    FixtureAwareRetriever,
    RecordingIndexWriter,
)

_INLINE_CORPUS = {
    "query": "How does photosynthesis convert light energy?",
    "document_title": "Custom corpus",
    "document_text": (
        "# Custom\n\n"
        "Photosynthesis uses chlorophyll during light-dependent reactions "
        "to make glucose."
    ),
    "expected_phrases": ["chlorophyll", "light-dependent reactions", "glucose"],
}


@pytest.fixture
def _wired_rag_runtime() -> None:
    set_token_counter(TiktokenTokenCounter())
    writer = RecordingIndexWriter()
    set_chunking_strategy(FakeChunkingStrategy())
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(FixtureAwareRetriever(writer))
    set_reranker(NoOpReranker())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    yield
    reset_retrieval_clients()
    reset_workflow_execution_config()


async def _collect_stream_events(**kwargs: object) -> list[object]:
    events: list[object] = []
    async for event in stream_rag_benchmark(**kwargs):
        events.append(event)
    return events


def test_list_benchmarks_includes_rag_entry() -> None:
    benchmarks = list_benchmarks()

    assert len(benchmarks) >= 1
    rag = next(item for item in benchmarks if item.id == "rag")
    assert rag.workflow_id == "rag-validation"
    assert rag.name
    assert rag.description


def test_get_benchmark_returns_none_for_unknown_id() -> None:
    assert get_benchmark("unknown") is None


async def test_stream_benchmark_unknown_id_yields_error_event() -> None:
    events: list[object] = []
    async for event in stream_benchmark("unknown"):
        events.append(event)

    assert len(events) == 1
    assert isinstance(events[0], BenchmarkErrorEvent)
    assert events[0].stage == "error"
    assert "not found" in events[0].message.lower()


async def test_stream_rag_dataset_benchmark_aggregates_scenarios(
    _wired_rag_runtime: None,
) -> None:
    from mcp_server.application.benchmark_runner import stream_rag_dataset_benchmark
    from mcp_server.domain.rag_hyperparameters import RagHyperparameters

    events: list[object] = []
    async for event in stream_rag_dataset_benchmark(
        hyperparameters=RagHyperparameters(
            retrieval_mode="vector",
            retrieve_limit=4,
            rerank_enabled=False,
            rerank_top_n=4,
        ),
        scenarios=_mock_scenarios(),
    ):
        events.append(event)

    assert isinstance(events[-1], BenchmarkCompleteEvent)
    complete = events[-1]
    assert complete.dataset_report is not None
    assert complete.dataset_report["scenario_count"] == 1
    assert complete.dataset_report["scenarios"]
    progress_with_scenario = [
        event
        for event in events
        if isinstance(event, BenchmarkProgressEvent) and event.scenario_id is not None
    ]
    assert progress_with_scenario
    assert progress_with_scenario[0].scenario_id == "SC0001"


async def test_stream_benchmark_rag_uses_test_dataset_path(
    _wired_rag_runtime: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mcp_server.application.benchmark_runner import stream_rag_dataset_benchmark

    async def _fake_dataset_stream(**_kwargs: object):
        yield BenchmarkProgressEvent(
            stage="indexing",
            progress=50,
            message="dataset",
            scenario_id="SC0001",
            scenario_index=1,
            scenario_total=1,
        )
        yield BenchmarkCompleteEvent(
            stage="complete",
            progress=100,
            message="done",
            state={},
            trace=[],
            dataset_report={"scenario_count": 1, "scenarios": []},
        )

    monkeypatch.setattr(
        "mcp_server.application.benchmark_runner.stream_rag_dataset_benchmark",
        _fake_dataset_stream,
    )

    events: list[object] = []
    async for event in stream_benchmark("rag", retrieve_limit=4, rerank_enabled=False):
        events.append(event)

    assert isinstance(events[-1], BenchmarkCompleteEvent)


async def test_stream_rag_benchmark_maps_known_nodes_to_progress_contract(
    _wired_rag_runtime: None,
) -> None:
    events = await _collect_stream_events(**_INLINE_CORPUS)
    progress_events = [event for event in events if isinstance(event, BenchmarkProgressEvent)]

    assert progress_events
    for event in progress_events:
        if event.node_id not in _RAG_NODE_PROGRESS:
            continue
        stage, progress, message = _RAG_NODE_PROGRESS[event.node_id]
        assert event.stage == stage
        assert event.progress == progress
        assert event.message == message
        assert event.step is not None
        assert event.total == len(_RAG_NODE_PROGRESS)


async def test_stream_rag_benchmark_ends_with_complete_event(
    _wired_rag_runtime: None,
) -> None:
    events = await _collect_stream_events(**_INLINE_CORPUS)

    assert isinstance(events[-1], BenchmarkCompleteEvent)
    complete = events[-1]
    assert complete.stage == "complete"
    assert complete.progress == 100
    assert complete.message == "Benchmark complete"
    assert complete.trace
    assert complete.state is not None


async def test_stream_rag_benchmark_progress_is_monotonic(
    _wired_rag_runtime: None,
) -> None:
    events = await _collect_stream_events(**_INLINE_CORPUS)
    progress_values = [
        event.progress
        for event in events
        if isinstance(event, BenchmarkProgressEvent)
    ]

    assert progress_values
    for earlier, later in zip(progress_values, progress_values[1:], strict=False):
        assert earlier <= later


def _mock_scenarios() -> list[RagSearchScenario]:
    return [
        RagSearchScenario(
            name="SC0001",
            query="How do I authenticate?",
            expected_phrases=("bearer token",),
            document_text="API keys are passed as a bearer token.",
            document_title="Auth guide",
        )
    ]


class _MockOptimizer:
    def __init__(self, scenarios: list[RagSearchScenario]) -> None:
        self._scenarios = scenarios
        self._search_space = RagHyperparameterSearchSpace(
            retrieval_modes=("vector",),
            retrieve_limits=(4, 8),
            rerank_enabled_values=(False,),
            rerank_top_ns=(6,),
        )

    def plan_combinations(self, *, max_combinations: int | None = None) -> list[RagHyperparameters]:
        return self._search_space.expand(max_combinations=max_combinations)

    async def evaluate_hyperparameters(self, hyperparameters: RagHyperparameters):
        from mcp_server.domain.rag_benchmarks import RagBenchmarkScores
        from mcp_server.domain.rag_hyperparameters import RagConfigScore, RagScenarioBenchmark

        coverage = 0.5 if hyperparameters.retrieve_limit < 8 else 1.0
        scenario_results = tuple(
            RagScenarioBenchmark(
                scenario_name=scenario.name,
                hyperparameters=hyperparameters,
                benchmarks=RagBenchmarkScores(
                    phrase_coverage=coverage,
                    phrase_chunk_rate=coverage,
                    any_phrase_hit=1.0 if coverage > 0 else 0.0,
                    first_phrase_rank_reciprocal=coverage,
                    expected_phrase_count=1,
                    matched_phrase_count=int(coverage),
                    retrieved_chunk_count=hyperparameters.retrieve_limit,
                ),
                validation_passed=coverage >= 1.0,
            )
            for scenario in self._scenarios
        )
        return RagConfigScore(
            hyperparameters=hyperparameters,
            mean_phrase_coverage=coverage,
            mean_first_phrase_rank_reciprocal=coverage,
            mean_gold_semantic_relevance=0.0,
            mean_gold_semantic_precision=0.0,
            validation_pass_rate=1.0 if coverage >= 1.0 else 0.0,
            scenario_results=scenario_results,
        )

    async def evaluate_combinations(self, *, max_combinations: int | None = None):
        combinations = self.plan_combinations(max_combinations=max_combinations)
        total = len(combinations)
        for index, hyperparameters in enumerate(combinations, start=1):
            score = await self.evaluate_hyperparameters(hyperparameters)
            yield index, total, score

    def finalize_from_scores(self, config_scores):
        best = RagHyperparameters(
            retrieval_mode="vector",
            retrieve_limit=8,
            rerank_enabled=False,
            rerank_top_n=6,
        )
        return OptimizedRagHyperparameters(
            optimized_at="2026-07-22T20:00:00+00:00",
            objective=OBJECTIVE_MEAN_PHRASE_COVERAGE,
            best_score=1.0,
            hyperparameters=best,
            search_space=self._search_space.as_dict(),
            results_summary=[],
        )

    async def optimize(self, *, max_combinations: int | None = None) -> OptimizedRagHyperparameters:
        config_scores = [
            score
            async for _, _, score in self.evaluate_combinations(
                max_combinations=max_combinations,
            )
        ]
        return self.finalize_from_scores(config_scores)


async def test_stream_rag_optimization_emits_expected_stages(tmp_path, monkeypatch) -> None:
    from mcp_server.application.agents.rag_validation import optimization_report as report_module

    monkeypatch.setattr(
        report_module,
        "save_optimization_report",
        lambda report, path=None: report_module.resolve_optimization_report_path(
            tmp_path / "optimization_report.json"
        ),
    )
    monkeypatch.setattr(
        "mcp_server.application.benchmark_runner.save_optimized_hyperparameters",
        lambda result, path=None: tmp_path / "optimized_hyperparameters.json",
    )

    events: list[object] = []
    async for event in stream_rag_optimization(
        scenarios=_mock_scenarios(),
        max_combinations=2,
        optimizer_factory=lambda scenarios: _MockOptimizer(scenarios),
    ):
        events.append(event)

    progress_stages = [
        event.stage
        for event in events
        if isinstance(event, RagOptimizationProgressEvent)
    ]
    assert progress_stages[0] == "baseline"
    assert progress_stages[-2:] == ["saving", "after"]
    searching_events = [
        event
        for event in events
        if isinstance(event, RagOptimizationProgressEvent) and event.stage == "searching"
    ]
    assert len(searching_events) == 3
    assert searching_events[0].combination_total == 2
    assert searching_events[0].combination_index is None
    assert searching_events[-1].combination_index == 2
    assert searching_events[-1].combination_total == 2
    assert isinstance(events[-1], RagOptimizationCompleteEvent)
    complete = events[-1]
    assert complete.report["scenario_count"] == 1
    assert complete.report["after"]["mean_phrase_coverage"] == 1.0
    assert complete.optimized_hyperparameters["retrieve_limit"] == 8


async def test_stream_rag_optimization_yields_error_when_no_scenarios(monkeypatch) -> None:
    monkeypatch.setattr(
        "mcp_server.application.benchmark_runner.load_test_dataset_scenarios",
        lambda **_kwargs: [],
    )

    events: list[object] = []
    async for event in stream_rag_optimization():
        events.append(event)

    assert len(events) == 1
    assert isinstance(events[0], RagOptimizationErrorEvent)
    assert events[0].stage == "error"
    assert "no eval scenarios" in events[0].message.lower()
