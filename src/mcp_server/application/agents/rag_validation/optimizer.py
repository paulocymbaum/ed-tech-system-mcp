"""Grid-search optimizer for RAG retrieval hyperparameters."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from mcp_server.application.agents.rag_validation.graph import run_rag_validation_graph
from mcp_server.application.agents.rag_validation.scenarios import RagSearchScenario
from mcp_server.application.agents.rag_validation.semantic_benchmarks import (
    enrich_benchmarks_with_gold_semantic,
)
from mcp_server.application.agents.rag_validation.state import RagValidationState
from mcp_server.domain.rag_benchmarks import (
    DEFAULT_GOLD_SEMANTIC_PRECISION_THRESHOLD,
    RagBenchmarkScores,
)
from mcp_server.domain.rag_hyperparameters import (
    OBJECTIVE_MEAN_GOLD_SEMANTIC_RELEVANCE,
    OBJECTIVE_MEAN_PHRASE_COVERAGE,
    OptimizedRagHyperparameters,
    RagConfigScore,
    RagHyperparameters,
    RagHyperparameterSearchSpace,
    RagScenarioBenchmark,
    score_config_results,
    select_best_config,
)


def default_rag_hyperparameter_search_space() -> RagHyperparameterSearchSpace:
    """Default retrieval grid used by the CLI and Benchmark UI optimizer."""
    return RagHyperparameterSearchSpace(
        retrieval_modes=("vector", "hybrid"),
        retrieve_limits=(4, 8, 10),
        rerank_enabled_values=(False, True),
        rerank_top_ns=(4, 6),
    )


RunRagValidation = Callable[..., Awaitable[RagValidationState]]


class RagHyperparameterOptimizer:
    """Evaluate retrieval hyperparameters against deterministic benchmark scenarios."""

    def __init__(
        self,
        *,
        search_space: RagHyperparameterSearchSpace,
        scenarios: list[RagSearchScenario],
        run_validation: RunRagValidation | None = None,
    ) -> None:
        self._search_space = search_space
        self._scenarios = scenarios
        self._run_validation = run_validation or run_rag_validation_graph

    def plan_combinations(self, *, max_combinations: int | None = None) -> list[RagHyperparameters]:
        return self._search_space.expand(max_combinations=max_combinations)

    async def evaluate_hyperparameters(
        self,
        hyperparameters: RagHyperparameters,
    ) -> RagConfigScore:
        """Score one hyperparameter set across all configured scenarios."""
        scenario_results = [
            await self._evaluate_scenario(hyperparameters, scenario) for scenario in self._scenarios
        ]
        return score_config_results(hyperparameters, scenario_results)

    async def evaluate_combinations(
        self,
        *,
        max_combinations: int | None = None,
    ) -> AsyncIterator[tuple[int, int, RagConfigScore]]:
        """Evaluate each hyperparameter combination, yielding index, total, and score."""
        if not self._scenarios:
            msg = "No benchmark scenarios to evaluate"
            raise ValueError(msg)
        combinations = self.plan_combinations(max_combinations=max_combinations)
        total = len(combinations)
        for index, hyperparameters in enumerate(combinations, start=1):
            score = await self.evaluate_hyperparameters(hyperparameters)
            yield index, total, score

    def finalize_from_scores(
        self,
        config_scores: list[RagConfigScore],
    ) -> OptimizedRagHyperparameters:
        """Select the best score and build the persisted optimization result."""
        best = select_best_config(config_scores)
        if best is None:
            msg = "No hyperparameter combinations to evaluate"
            raise ValueError(msg)

        return OptimizedRagHyperparameters(
            optimized_at=datetime.now(UTC).isoformat(),
            objective=OBJECTIVE_MEAN_GOLD_SEMANTIC_RELEVANCE
            if best.mean_gold_semantic_relevance > 0.0
            else OBJECTIVE_MEAN_PHRASE_COVERAGE,
            best_score=best.mean_gold_semantic_relevance
            if best.mean_gold_semantic_relevance > 0.0
            else best.mean_phrase_coverage,
            hyperparameters=best.hyperparameters,
            search_space=self._search_space.as_dict(),
            results_summary=[score.as_summary_dict() for score in config_scores],
        )

    async def optimize(self, *, max_combinations: int | None = None) -> OptimizedRagHyperparameters:
        config_scores = [
            score
            async for _, _, score in self.evaluate_combinations(
                max_combinations=max_combinations,
            )
        ]
        return self.finalize_from_scores(config_scores)

    async def evaluate_scenario(
        self,
        hyperparameters: RagHyperparameters,
        scenario: RagSearchScenario,
    ) -> RagScenarioBenchmark:
        """Score a single scenario with the given hyperparameters."""
        return await self._evaluate_scenario(hyperparameters, scenario)

    async def _evaluate_scenario(
        self,
        hyperparameters: RagHyperparameters,
        scenario: RagSearchScenario,
    ) -> RagScenarioBenchmark:
        kwargs: dict[str, Any] = {
            "retrieval_mode": hyperparameters.retrieval_mode,
            "retrieve_limit": hyperparameters.retrieve_limit,
            "rerank_enabled": hyperparameters.rerank_enabled,
            "rerank_top_n": hyperparameters.rerank_top_n,
            "expected_phrases": list(scenario.expected_phrases),
        }
        if scenario.document_text is not None:
            kwargs["document_text"] = scenario.document_text
        if scenario.fixture_path is not None:
            kwargs["fixture_path"] = scenario.fixture_path
        if scenario.document_title is not None:
            kwargs["document_title"] = scenario.document_title

        state = await self._run_validation(scenario.query, **kwargs)
        benchmarks = _benchmarks_from_state(state)
        if scenario.gold_answer:
            chunks = state.get("reranked_chunks") or state.get("retrieved_chunks", [])
            benchmarks = await enrich_benchmarks_with_gold_semantic(
                benchmarks,
                gold_answer=scenario.gold_answer,
                chunks=chunks,
            )
        validation_passed = _validation_passed_for_scenario(
            state=state,
            benchmarks=benchmarks,
            has_gold_answer=bool(scenario.gold_answer),
        )
        return RagScenarioBenchmark(
            scenario_name=scenario.name,
            hyperparameters=hyperparameters,
            benchmarks=benchmarks,
            validation_passed=validation_passed,
        )


def _validation_passed_for_scenario(
    *,
    state: RagValidationState,
    benchmarks: RagBenchmarkScores,
    has_gold_answer: bool,
) -> bool:
    if has_gold_answer:
        return benchmarks.gold_semantic_relevance >= DEFAULT_GOLD_SEMANTIC_PRECISION_THRESHOLD
    return bool(state.get("validation_passed"))


def _benchmarks_from_state(state: RagValidationState) -> RagBenchmarkScores:
    raw = state.get("rag_benchmarks", {})
    if not isinstance(raw, dict) or not raw:
        return RagBenchmarkScores(
            phrase_coverage=0.0,
            phrase_chunk_rate=0.0,
            any_phrase_hit=0.0,
            first_phrase_rank_reciprocal=0.0,
            expected_phrase_count=0,
            matched_phrase_count=0,
            retrieved_chunk_count=0,
        )
    return RagBenchmarkScores(
        phrase_coverage=float(raw.get("phrase_coverage", 0.0)),
        phrase_chunk_rate=float(raw.get("phrase_chunk_rate", 0.0)),
        any_phrase_hit=float(raw.get("any_phrase_hit", 0.0)),
        first_phrase_rank_reciprocal=float(raw.get("first_phrase_rank_reciprocal", 0.0)),
        expected_phrase_count=int(raw.get("expected_phrase_count", 0)),
        matched_phrase_count=int(raw.get("matched_phrase_count", 0)),
        retrieved_chunk_count=int(raw.get("retrieved_chunk_count", 0)),
    )
