"""Orchestration and persistence for RAG optimization before/after reports."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from mcp_server.application.agents.rag_validation.fixture import (
    OPTIMIZATION_REPORT_PATH,
    resolve_repo_root,
)
from mcp_server.application.agents.rag_validation.optimizer import RagHyperparameterOptimizer
from mcp_server.domain.optimization_report import (
    OptimizationPhaseResult,
    RagOptimizationReport,
    ScenarioOptimizationRow,
    build_optimization_report,
)
from mcp_server.domain.rag_hyperparameters import (
    OBJECTIVE_MEAN_PHRASE_COVERAGE,
    OptimizedRagHyperparameters,
    RagConfigScore,
    RagHyperparameters,
)


def default_baseline_hyperparameters() -> RagHyperparameters:
    """Baseline retrieval settings used for the before optimization phase."""
    return RagHyperparameters(
        retrieval_mode="vector",
        retrieve_limit=10,
        rerank_enabled=False,
        rerank_top_n=6,
    )


def config_score_to_phase_result(
    score: RagConfigScore,
    *,
    scenario_lookup: dict[str, str] | None = None,
) -> OptimizationPhaseResult:
    """Convert an optimizer config score into a report phase result."""
    lookup = scenario_lookup or {}
    scenarios = tuple(
        ScenarioOptimizationRow(
            scenario_name=result.scenario_name,
            query=lookup.get(result.scenario_name, result.scenario_name),
            phrase_coverage=result.benchmarks.phrase_coverage,
            first_phrase_rank_reciprocal=result.benchmarks.first_phrase_rank_reciprocal,
            gold_semantic_relevance=result.benchmarks.gold_semantic_relevance,
            gold_semantic_precision=result.benchmarks.gold_semantic_precision,
            validation_passed=result.validation_passed,
        )
        for result in score.scenario_results
    )
    return OptimizationPhaseResult(
        hyperparameters=score.hyperparameters,
        mean_phrase_coverage=score.mean_phrase_coverage,
        mean_first_phrase_rank_reciprocal=score.mean_first_phrase_rank_reciprocal,
        mean_gold_semantic_relevance=score.mean_gold_semantic_relevance,
        mean_gold_semantic_precision=score.mean_gold_semantic_precision,
        validation_pass_rate=score.validation_pass_rate,
        scenarios=scenarios,
    )


def build_report_from_optimization(
    *,
    before_score: RagConfigScore,
    optimized: OptimizedRagHyperparameters,
    after_score: RagConfigScore,
    scenario_lookup: dict[str, str] | None = None,
) -> RagOptimizationReport:
    """Build a before/after report from optimizer evaluation scores."""
    lookup = scenario_lookup or {}
    return build_optimization_report(
        created_at=datetime.now(UTC).isoformat(),
        optimized_at=optimized.optimized_at,
        before=config_score_to_phase_result(before_score, scenario_lookup=lookup),
        after=config_score_to_phase_result(after_score, scenario_lookup=lookup),
        objective=OBJECTIVE_MEAN_PHRASE_COVERAGE,
    )


async def evaluate_hyperparameters(
    optimizer: RagHyperparameterOptimizer,
    hyperparameters: RagHyperparameters,
) -> RagConfigScore:
    """Evaluate all optimizer scenarios under a single hyperparameter set."""
    return await optimizer.evaluate_hyperparameters(hyperparameters)


def resolve_optimization_report_path(path: str | Path | None = None) -> Path:
    if path is None:
        return OPTIMIZATION_REPORT_PATH
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolve_repo_root() / candidate
    return candidate


def load_optimization_report(path: str | Path | None = None) -> RagOptimizationReport | None:
    target = resolve_optimization_report_path(path)
    if not target.is_file():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Optimization report must contain a JSON object: {target}"
        raise ValueError(msg)
    return RagOptimizationReport.from_dict(payload)


def save_optimization_report(
    report: RagOptimizationReport,
    path: str | Path | None = None,
) -> Path:
    target = resolve_optimization_report_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
