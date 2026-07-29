"""Tests for optimization report domain logic and persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server.application.agents.rag_validation.optimization_report import (
    build_report_from_optimization,
    load_optimization_report,
    save_optimization_report,
)
from mcp_server.domain.optimization_report import (
    OptimizationPhaseResult,
    RagOptimizationReport,
    ScenarioOptimizationRow,
    build_optimization_report,
    compute_optimization_diff,
    derive_expected_phrases_from_chunk_texts,
    derive_expected_phrases_from_gold_answer,
    filter_phrases_present_in_document,
)
from mcp_server.domain.rag_benchmarks import RagBenchmarkScores
from mcp_server.domain.rag_hyperparameters import (
    OBJECTIVE_MEAN_PHRASE_COVERAGE,
    OptimizedRagHyperparameters,
    RagConfigScore,
    RagHyperparameters,
    RagScenarioBenchmark,
)


def test_derive_expected_phrases_from_gold_answer_splits_clauses() -> None:
    phrases = derive_expected_phrases_from_gold_answer(
        "API keys are passed as a bearer token, and requests are rate limited per minute."
    )
    assert phrases == (
        "API keys are passed as a bearer token",
        "and requests are rate limited per minute",
    )


def test_derive_expected_phrases_from_gold_answer_skips_no_answer_marker() -> None:
    assert derive_expected_phrases_from_gold_answer("NO_ANSWER_IN_CORPUS") == ()


def test_derive_expected_phrases_from_chunk_texts_extracts_quoted_titles() -> None:
    phrases = derive_expected_phrases_from_chunk_texts(
        (
            "In this section of 'Service-to-service auth and endpoint — engineering guide 2024' "
            "focuses on authentication patterns.",
            "This part of 'Service-to-service auth and endpoint — engineering guide 2024' "
            "covers request shapes.",
        )
    )
    assert phrases == ("Service-to-service auth and endpoint — engineering guide 2024",)


def test_filter_phrases_present_in_document_keeps_matching_segments() -> None:
    document = "API keys are passed as a bearer token. Bearer tokens authenticate API requests."
    phrases = filter_phrases_present_in_document(
        ("API keys are passed as a bearer token", "missing phrase"),
        document,
    )
    assert phrases == ("API keys are passed as a bearer token",)


def test_compute_optimization_diff_reports_deltas() -> None:
    hyperparameters = RagHyperparameters(
        retrieval_mode="vector",
        retrieve_limit=10,
        rerank_enabled=False,
        rerank_top_n=6,
    )
    before = OptimizationPhaseResult(
        hyperparameters=hyperparameters,
        mean_phrase_coverage=0.5,
        mean_first_phrase_rank_reciprocal=0.25,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=0.5,
        scenarios=(),
    )
    after = OptimizationPhaseResult(
        hyperparameters=hyperparameters,
        mean_phrase_coverage=0.75,
        mean_first_phrase_rank_reciprocal=0.5,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=1.0,
        scenarios=(),
    )

    diff = compute_optimization_diff(before, after)

    assert diff.mean_phrase_coverage_delta == 0.25
    assert diff.mean_first_phrase_rank_reciprocal_delta == 0.25
    assert diff.validation_pass_rate_delta == 0.5


def test_build_report_from_optimization_round_trips_through_json(tmp_path: Path) -> None:
    hyperparameters = RagHyperparameters(
        retrieval_mode="vector",
        retrieve_limit=8,
        rerank_enabled=False,
        rerank_top_n=6,
    )
    scenario_result = RagScenarioBenchmark(
        scenario_name="SC0001",
        hyperparameters=hyperparameters,
        benchmarks=RagBenchmarkScores(
            phrase_coverage=0.5,
            phrase_chunk_rate=0.5,
            any_phrase_hit=1.0,
            first_phrase_rank_reciprocal=0.5,
            expected_phrase_count=2,
            matched_phrase_count=1,
            retrieved_chunk_count=4,
        ),
        validation_passed=False,
    )
    before_score = RagConfigScore(
        hyperparameters=hyperparameters,
        mean_phrase_coverage=0.5,
        mean_first_phrase_rank_reciprocal=0.5,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=0.0,
        scenario_results=(scenario_result,),
    )
    after_score = RagConfigScore(
        hyperparameters=hyperparameters,
        mean_phrase_coverage=1.0,
        mean_first_phrase_rank_reciprocal=1.0,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=1.0,
        scenario_results=(
            RagScenarioBenchmark(
                scenario_name="SC0001",
                hyperparameters=hyperparameters,
                benchmarks=RagBenchmarkScores(
                    phrase_coverage=1.0,
                    phrase_chunk_rate=1.0,
                    any_phrase_hit=1.0,
                    first_phrase_rank_reciprocal=1.0,
                    expected_phrase_count=2,
                    matched_phrase_count=2,
                    retrieved_chunk_count=4,
                ),
                validation_passed=True,
            ),
        ),
    )
    optimized = OptimizedRagHyperparameters(
        optimized_at="2026-07-22T20:00:00+00:00",
        objective=OBJECTIVE_MEAN_PHRASE_COVERAGE,
        best_score=1.0,
        hyperparameters=hyperparameters,
        search_space={},
        results_summary=[],
    )

    report = build_report_from_optimization(
        before_score=before_score,
        optimized=optimized,
        after_score=after_score,
        scenario_lookup={"SC0001": "How do I authenticate?"},
    )
    target = save_optimization_report(report, tmp_path / "optimization_report.json")
    loaded = load_optimization_report(target)

    assert loaded is not None
    assert loaded.scenario_count == 1
    assert loaded.before.scenarios[0].query == "How do I authenticate?"
    assert loaded.after.mean_phrase_coverage == 1.0
    assert loaded.diff.mean_phrase_coverage_delta == 0.5


def test_build_optimization_report_requires_scenario_rows() -> None:
    hyperparameters = RagHyperparameters(
        retrieval_mode="vector",
        retrieve_limit=10,
        rerank_enabled=False,
        rerank_top_n=6,
    )
    phase = OptimizationPhaseResult(
        hyperparameters=hyperparameters,
        mean_phrase_coverage=1.0,
        mean_first_phrase_rank_reciprocal=1.0,
        mean_gold_semantic_relevance=0.0,
        mean_gold_semantic_precision=0.0,
        validation_pass_rate=1.0,
        scenarios=(
            ScenarioOptimizationRow(
                scenario_name="SC0001",
                query="query",
                phrase_coverage=1.0,
                first_phrase_rank_reciprocal=1.0,
                gold_semantic_relevance=0.0,
                gold_semantic_precision=0.0,
                validation_passed=True,
            ),
        ),
    )
    report = build_optimization_report(
        created_at="2026-07-22T20:00:00+00:00",
        optimized_at="2026-07-22T20:05:00+00:00",
        before=phase,
        after=phase,
    )
    assert report.scenario_count == 1


def test_rag_optimization_report_from_dict_raises_on_invalid_before() -> None:
    with pytest.raises(ValueError, match="before/after must be objects"):
        RagOptimizationReport.from_dict(
            {
                "created_at": "2026-07-22T20:00:00+00:00",
                "scenario_count": 0,
                "before": "invalid",
                "after": {},
                "diff": {},
                "optimized_at": "2026-07-22T20:05:00+00:00",
            }
        )


def test_load_optimization_report_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_optimization_report(tmp_path / "missing.json") is None
