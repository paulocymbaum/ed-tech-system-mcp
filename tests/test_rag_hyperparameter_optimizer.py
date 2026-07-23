"""Tests for RAG hyperparameter search space, scoring, and optimizer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.application.agents.rag_validation.fixture import (
    OPTIMIZED_HYPERPARAMETERS_PATH,
    load_optimized_hyperparameters,
    save_optimized_hyperparameters,
)
from mcp_server.application.agents.rag_validation.optimizer import RagHyperparameterOptimizer
from mcp_server.application.agents.rag_validation.scenarios import (
    DEFAULT_SCENARIOS_PATH,
    RagSearchScenario,
    load_search_scenarios,
)
from mcp_server.domain.rag_benchmarks import RagBenchmarkScores
from mcp_server.domain.rag_hyperparameters import (
    OBJECTIVE_MEAN_PHRASE_COVERAGE,
    OptimizedRagHyperparameters,
    RagConfigScore,
    RagHyperparameters,
    RagHyperparameterSearchSpace,
    RagScenarioBenchmark,
    compare_config_scores,
    score_config_results,
    select_best_config,
)


def _hyperparameters(**overrides: object) -> RagHyperparameters:
    base = {
        "retrieval_mode": "vector",
        "retrieve_limit": 10,
        "rerank_enabled": False,
        "rerank_top_n": 6,
    }
    base.update(overrides)
    return RagHyperparameters.from_dict(base)


def _scenario_benchmark(
    *,
    name: str,
    hyperparameters: RagHyperparameters,
    phrase_coverage: float,
    reciprocal: float,
    validation_passed: bool,
) -> RagScenarioBenchmark:
    return RagScenarioBenchmark(
        scenario_name=name,
        hyperparameters=hyperparameters,
        benchmarks=RagBenchmarkScores(
            phrase_coverage=phrase_coverage,
            phrase_chunk_rate=phrase_coverage,
            any_phrase_hit=1.0 if phrase_coverage > 0 else 0.0,
            first_phrase_rank_reciprocal=reciprocal,
            expected_phrase_count=3,
            matched_phrase_count=int(phrase_coverage * 3),
            retrieved_chunk_count=4,
        ),
        validation_passed=validation_passed,
    )


def test_search_space_grid_expansion_is_deterministic() -> None:
    space = RagHyperparameterSearchSpace(
        retrieval_modes=("vector", "hybrid"),
        retrieve_limits=(4, 8),
        rerank_enabled_values=(False,),
        rerank_top_ns=(4, 6),
    )
    combos = space.expand()
    assert len(combos) == 8
    assert combos[0] == _hyperparameters(retrieval_mode="vector", retrieve_limit=4, rerank_top_n=4)
    assert combos[-1] == _hyperparameters(retrieval_mode="hybrid", retrieve_limit=8, rerank_top_n=6)


def test_search_space_respects_max_combinations() -> None:
    space = RagHyperparameterSearchSpace(
        retrieval_modes=("vector", "hybrid"),
        retrieve_limits=(4, 8, 10),
        rerank_enabled_values=(False, True),
        rerank_top_ns=(4, 6),
    )
    combos = space.expand(max_combinations=3)
    assert len(combos) == 3
    assert combos == space.expand()[:3]


def test_search_space_explicit_combinations_override_grid() -> None:
    explicit = (
        _hyperparameters(retrieve_limit=3),
        _hyperparameters(retrieve_limit=7, rerank_enabled=True),
    )
    space = RagHyperparameterSearchSpace(
        retrieval_modes=("vector",),
        retrieve_limits=(99,),
        explicit_combinations=explicit,
    )
    assert space.expand() == list(explicit)


def test_T04_search_space_from_dict_round_trip() -> None:
    original = RagHyperparameterSearchSpace(
        retrieval_modes=("vector", "hybrid"),
        retrieve_limits=(4, 8),
        rerank_enabled_values=(False, True),
        rerank_top_ns=(4,),
        explicit_combinations=(_hyperparameters(retrieve_limit=6),),
    )
    restored = RagHyperparameterSearchSpace.from_dict(original.as_dict())
    assert restored == original
    assert restored.expand() == original.expand()


def test_score_config_results_aggregates_scenarios() -> None:
    params = _hyperparameters()
    results = [
        _scenario_benchmark(
            name="a",
            hyperparameters=params,
            phrase_coverage=1.0,
            reciprocal=1.0,
            validation_passed=True,
        ),
        _scenario_benchmark(
            name="b",
            hyperparameters=params,
            phrase_coverage=0.5,
            reciprocal=0.5,
            validation_passed=False,
        ),
    ]
    score = score_config_results(params, results)
    assert score.mean_phrase_coverage == 0.75
    assert score.mean_first_phrase_rank_reciprocal == 0.75
    assert score.validation_pass_rate == 0.5


def test_T06_score_config_results_empty_returns_zeros() -> None:
    score = score_config_results(_hyperparameters(), [])
    assert score.mean_phrase_coverage == 0.0
    assert score.mean_first_phrase_rank_reciprocal == 0.0
    assert score.validation_pass_rate == 0.0
    assert score.scenario_results == ()


def test_compare_config_scores_uses_tie_breakers() -> None:
    params = _hyperparameters()
    better = RagConfigScore(
        hyperparameters=params,
        mean_phrase_coverage=1.0,
        mean_first_phrase_rank_reciprocal=0.5,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=1.0,
        scenario_results=(),
    )
    worse_coverage = RagConfigScore(
        hyperparameters=params,
        mean_phrase_coverage=0.8,
        mean_first_phrase_rank_reciprocal=1.0,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=1.0,
        scenario_results=(),
    )
    tied_coverage_better_reciprocal = RagConfigScore(
        hyperparameters=params,
        mean_phrase_coverage=1.0,
        mean_first_phrase_rank_reciprocal=1.0,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=0.0,
        scenario_results=(),
    )
    tied_reciprocal_better_validation = RagConfigScore(
        hyperparameters=params,
        mean_phrase_coverage=1.0,
        mean_first_phrase_rank_reciprocal=1.0,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=1.0,
        scenario_results=(),
    )

    assert compare_config_scores(better, worse_coverage) > 0
    assert compare_config_scores(tied_coverage_better_reciprocal, better) > 0
    assert (
        compare_config_scores(tied_reciprocal_better_validation, tied_coverage_better_reciprocal) > 0
    )
    assert select_best_config([worse_coverage, better, tied_reciprocal_better_validation]) == (
        tied_reciprocal_better_validation
    )


def test_T08_select_best_config_returns_none_when_empty() -> None:
    assert select_best_config([]) is None


def test_T09_optimized_from_dict_rejects_unsupported_objective() -> None:
    payload = OptimizedRagHyperparameters(
        optimized_at="2026-07-22T20:00:00+00:00",
        objective=OBJECTIVE_MEAN_PHRASE_COVERAGE,
        best_score=0.5,
        hyperparameters=_hyperparameters(),
        search_space={},
        results_summary=[],
    ).as_dict()
    payload["objective"] = "mean_mrr"
    with pytest.raises(ValueError, match="Unsupported optimization objective"):
        OptimizedRagHyperparameters.from_dict(payload)


def test_optimized_hyperparameters_json_round_trip(tmp_path: Path) -> None:
    result = OptimizedRagHyperparameters(
        optimized_at="2026-07-22T20:00:00+00:00",
        objective=OBJECTIVE_MEAN_PHRASE_COVERAGE,
        best_score=0.95,
        hyperparameters=_hyperparameters(retrieve_limit=8),
        search_space={"retrieve_limits": [4, 8]},
        results_summary=[{"mean_phrase_coverage": 0.95}],
    )
    target = tmp_path / "optimized.json"
    written = save_optimized_hyperparameters(result, target)
    loaded = load_optimized_hyperparameters(written)
    assert loaded == result
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["objective"] == OBJECTIVE_MEAN_PHRASE_COVERAGE
    assert payload["hyperparameters"]["retrieve_limit"] == 8


def test_load_search_scenarios_from_bundled_fixture() -> None:
    assert DEFAULT_SCENARIOS_PATH.is_file()
    scenarios = load_search_scenarios()
    assert len(scenarios) >= 1
    assert scenarios[0].name == "default"
    assert "chlorophyll" in scenarios[0].expected_phrases


def test_T14_load_search_scenarios_from_custom_json_file(tmp_path: Path) -> None:
    scenarios_path = tmp_path / "search_scenarios.json"
    scenarios_path.write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "name": "custom",
                        "query": "What is ATP?",
                        "expected_phrases": ["adenosine triphosphate"],
                        "document_text": "ATP stores cellular energy.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    scenarios = load_search_scenarios(scenarios_path)
    assert len(scenarios) == 1
    assert scenarios[0].name == "custom"
    assert scenarios[0].query == "What is ATP?"
    assert scenarios[0].expected_phrases == ("adenosine triphosphate",)
    assert scenarios[0].document_text == "ATP stores cellular energy."


def test_T15_load_search_scenarios_falls_back_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing_scenarios.json"
    scenarios = load_search_scenarios(missing)
    assert len(scenarios) == 1
    assert scenarios[0].name == "default"
    assert "chlorophyll" in scenarios[0].expected_phrases
    assert scenarios[0].document_text is not None


def test_load_optimized_hyperparameters_returns_none_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert load_optimized_hyperparameters(missing) is None


@pytest.mark.asyncio
async def test_optimizer_selects_best_configuration_with_mock_runner() -> None:
    calls: list[dict[str, object]] = []

    async def fake_runner(query: str | None = None, **kwargs: object) -> dict[str, object]:
        calls.append({"query": query, **kwargs})
        retrieve_limit = int(kwargs.get("retrieve_limit", 10))
        phrase_coverage = 1.0 if retrieve_limit >= 8 else 0.5
        validation_passed = retrieve_limit >= 8
        return {
            "validation_passed": validation_passed,
            "rag_benchmarks": {
                "phrase_coverage": phrase_coverage,
                "phrase_chunk_rate": phrase_coverage,
                "any_phrase_hit": 1.0 if phrase_coverage > 0 else 0.0,
                "first_phrase_rank_reciprocal": phrase_coverage,
                "expected_phrase_count": 3,
                "matched_phrase_count": int(phrase_coverage * 3),
                "retrieved_chunk_count": retrieve_limit,
            },
        }

    scenarios = [
        RagSearchScenario(
            name="fixture",
            query="How does photosynthesis convert light energy?",
            expected_phrases=("chlorophyll", "glucose"),
            document_text="Photosynthesis uses chlorophyll to make glucose.",
        )
    ]
    search_space = RagHyperparameterSearchSpace(
        retrieval_modes=("vector",),
        retrieve_limits=(4, 8),
        rerank_enabled_values=(False,),
        rerank_top_ns=(6,),
    )
    optimizer = RagHyperparameterOptimizer(
        search_space=search_space,
        scenarios=scenarios,
        run_validation=fake_runner,
    )

    result = await optimizer.optimize()
    assert result.best_score == 1.0
    assert result.hyperparameters.retrieve_limit == 8
    assert len(calls) == 2
    assert len(result.results_summary) == 2


@pytest.mark.asyncio
async def test_T17_optimizer_forwards_hyperparameters_to_runner() -> None:
    calls: list[dict[str, object]] = []

    async def fake_runner(query: str | None = None, **kwargs: object) -> dict[str, object]:
        calls.append({"query": query, **kwargs})
        return {
            "validation_passed": True,
            "rag_benchmarks": {
                "phrase_coverage": 1.0,
                "phrase_chunk_rate": 1.0,
                "any_phrase_hit": 1.0,
                "first_phrase_rank_reciprocal": 1.0,
                "expected_phrase_count": 1,
                "matched_phrase_count": 1,
                "retrieved_chunk_count": 1,
            },
        }

    scenarios = [
        RagSearchScenario(
            name="forwarding",
            query="How does photosynthesis work?",
            expected_phrases=("chlorophyll",),
            document_text="Chlorophyll captures light.",
        )
    ]
    search_space = RagHyperparameterSearchSpace(
        retrieval_modes=("hybrid",),
        retrieve_limits=(6,),
        rerank_enabled_values=(True,),
        rerank_top_ns=(4,),
        explicit_combinations=None,
    )
    optimizer = RagHyperparameterOptimizer(
        search_space=search_space,
        scenarios=scenarios,
        run_validation=fake_runner,
    )

    await optimizer.optimize()

    assert len(calls) == 1
    call = calls[0]
    assert call["query"] == "How does photosynthesis work?"
    assert call["retrieval_mode"] == "hybrid"
    assert call["retrieve_limit"] == 6
    assert call["rerank_enabled"] is True
    assert call["rerank_top_n"] == 4
    assert call["expected_phrases"] == ["chlorophyll"]
    assert call["document_text"] == "Chlorophyll captures light."


@pytest.mark.asyncio
async def test_T18_optimizer_raises_when_scenarios_empty() -> None:
    async def fake_runner(**_: object) -> dict[str, object]:
        return {"validation_passed": True, "rag_benchmarks": {}}

    optimizer = RagHyperparameterOptimizer(
        search_space=RagHyperparameterSearchSpace(retrieve_limits=(4,)),
        scenarios=[],
        run_validation=fake_runner,
    )
    with pytest.raises(ValueError, match="No benchmark scenarios"):
        await optimizer.optimize()


def test_bundled_optimized_path_constant_points_at_fixture_dir() -> None:
    assert OPTIMIZED_HYPERPARAMETERS_PATH.name == "optimized_hyperparameters.json"
    assert OPTIMIZED_HYPERPARAMETERS_PATH.parent.name == "rag_validation"
