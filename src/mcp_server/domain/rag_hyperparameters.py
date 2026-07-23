"""Pure types and scoring logic for RAG hyperparameter grid search."""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Literal

from mcp_server.domain.rag_benchmarks import RagBenchmarkScores, RetrievalMode

OBJECTIVE_MEAN_PHRASE_COVERAGE: Literal["mean_phrase_coverage"] = "mean_phrase_coverage"
OBJECTIVE_MEAN_GOLD_SEMANTIC_RELEVANCE: Literal["mean_gold_semantic_relevance"] = (
    "mean_gold_semantic_relevance"
)


@dataclass(frozen=True, slots=True)
class RagHyperparameters:
    """Tunable retrieval knobs for RAG validation and optimization."""

    retrieval_mode: RetrievalMode
    retrieve_limit: int
    rerank_enabled: bool
    rerank_top_n: int

    def as_dict(self) -> dict[str, str | int | bool]:
        return {
            "retrieval_mode": self.retrieval_mode,
            "retrieve_limit": self.retrieve_limit,
            "rerank_enabled": self.rerank_enabled,
            "rerank_top_n": self.rerank_top_n,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RagHyperparameters:
        return cls(
            retrieval_mode=_coerce_retrieval_mode(payload["retrieval_mode"]),
            retrieve_limit=int(payload["retrieve_limit"]),
            rerank_enabled=bool(payload["rerank_enabled"]),
            rerank_top_n=int(payload["rerank_top_n"]),
        )


@dataclass(frozen=True, slots=True)
class RagHyperparameterSearchSpace:
    """Grid or explicit list of retrieval hyperparameter combinations."""

    retrieval_modes: tuple[RetrievalMode, ...] = ("vector",)
    retrieve_limits: tuple[int, ...] = (10,)
    rerank_enabled_values: tuple[bool, ...] = (False,)
    rerank_top_ns: tuple[int, ...] = (6,)
    explicit_combinations: tuple[RagHyperparameters, ...] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "retrieval_modes": list(self.retrieval_modes),
            "retrieve_limits": list(self.retrieve_limits),
            "rerank_enabled_values": list(self.rerank_enabled_values),
            "rerank_top_ns": list(self.rerank_top_ns),
        }
        if self.explicit_combinations is not None:
            payload["explicit_combinations"] = [
                combo.as_dict() for combo in self.explicit_combinations
            ]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RagHyperparameterSearchSpace:
        explicit_raw = payload.get("explicit_combinations")
        explicit: tuple[RagHyperparameters, ...] | None = None
        if isinstance(explicit_raw, list) and explicit_raw:
            explicit = tuple(RagHyperparameters.from_dict(item) for item in explicit_raw)
        return cls(
            retrieval_modes=_coerce_mode_tuple(payload.get("retrieval_modes"), ("vector",)),
            retrieve_limits=_coerce_int_tuple(payload.get("retrieve_limits"), (10,)),
            rerank_enabled_values=_coerce_bool_tuple(
                payload.get("rerank_enabled_values"),
                (False,),
            ),
            rerank_top_ns=_coerce_int_tuple(payload.get("rerank_top_ns"), (6,)),
            explicit_combinations=explicit,
        )

    def expand(self, *, max_combinations: int | None = None) -> list[RagHyperparameters]:
        """Return hyperparameter combinations in deterministic order."""
        if self.explicit_combinations:
            combos = list(self.explicit_combinations)
        else:
            combos = [
                RagHyperparameters(
                    retrieval_mode=mode,
                    retrieve_limit=limit,
                    rerank_enabled=rerank_enabled,
                    rerank_top_n=rerank_top_n,
                )
                for mode, limit, rerank_enabled, rerank_top_n in itertools.product(
                    self.retrieval_modes,
                    self.retrieve_limits,
                    self.rerank_enabled_values,
                    self.rerank_top_ns,
                )
            ]
        if max_combinations is not None and max_combinations >= 0:
            return combos[:max_combinations]
        return combos


@dataclass(frozen=True, slots=True)
class RagScenarioBenchmark:
    """Benchmark outcome for one scenario under one hyperparameter set."""

    scenario_name: str
    hyperparameters: RagHyperparameters
    benchmarks: RagBenchmarkScores
    validation_passed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "hyperparameters": self.hyperparameters.as_dict(),
            "benchmarks": self.benchmarks.as_dict(),
            "validation_passed": self.validation_passed,
        }


@dataclass(frozen=True, slots=True)
class RagConfigScore:
    """Aggregated score for one hyperparameter configuration across scenarios."""

    hyperparameters: RagHyperparameters
    mean_phrase_coverage: float
    mean_first_phrase_rank_reciprocal: float
    mean_gold_semantic_relevance: float
    mean_gold_semantic_precision: float
    validation_pass_rate: float
    scenario_results: tuple[RagScenarioBenchmark, ...]

    def as_summary_dict(self) -> dict[str, Any]:
        return {
            "hyperparameters": self.hyperparameters.as_dict(),
            "mean_phrase_coverage": self.mean_phrase_coverage,
            "mean_first_phrase_rank_reciprocal": self.mean_first_phrase_rank_reciprocal,
            "mean_gold_semantic_relevance": self.mean_gold_semantic_relevance,
            "mean_gold_semantic_precision": self.mean_gold_semantic_precision,
            "validation_pass_rate": self.validation_pass_rate,
            "scenario_results": [result.as_dict() for result in self.scenario_results],
        }


@dataclass(frozen=True, slots=True)
class OptimizedRagHyperparameters:
    """Persisted output of a hyperparameter optimization run."""

    optimized_at: str
    objective: Literal["mean_phrase_coverage", "mean_gold_semantic_relevance"]
    best_score: float
    hyperparameters: RagHyperparameters
    search_space: dict[str, Any]
    results_summary: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "optimized_at": self.optimized_at,
            "objective": self.objective,
            "best_score": self.best_score,
            "hyperparameters": self.hyperparameters.as_dict(),
            "search_space": self.search_space,
            "results_summary": self.results_summary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> OptimizedRagHyperparameters:
        objective_raw = payload.get("objective", OBJECTIVE_MEAN_PHRASE_COVERAGE)
        if objective_raw not in (
            OBJECTIVE_MEAN_PHRASE_COVERAGE,
            OBJECTIVE_MEAN_GOLD_SEMANTIC_RELEVANCE,
        ):
            msg = f"Unsupported optimization objective: {objective_raw}"
            raise ValueError(msg)
        return cls(
            optimized_at=str(payload["optimized_at"]),
            objective=objective_raw,  # type: ignore[arg-type]
            best_score=float(payload["best_score"]),
            hyperparameters=RagHyperparameters.from_dict(payload["hyperparameters"]),
            search_space=dict(payload["search_space"]),
            results_summary=list(payload.get("results_summary", [])),
        )


def score_config_results(
    hyperparameters: RagHyperparameters,
    scenario_results: list[RagScenarioBenchmark],
) -> RagConfigScore:
    """Aggregate scenario benchmarks into a single config score."""
    if not scenario_results:
        return RagConfigScore(
            hyperparameters=hyperparameters,
            mean_phrase_coverage=0.0,
            mean_first_phrase_rank_reciprocal=0.0,
            mean_gold_semantic_relevance=0.0,
            mean_gold_semantic_precision=0.0,
            validation_pass_rate=0.0,
            scenario_results=(),
        )

    count = len(scenario_results)
    mean_phrase_coverage = round(
        sum(result.benchmarks.phrase_coverage for result in scenario_results) / count,
        4,
    )
    mean_first_phrase_rank_reciprocal = round(
        sum(result.benchmarks.first_phrase_rank_reciprocal for result in scenario_results) / count,
        4,
    )
    mean_gold_semantic_relevance = round(
        sum(result.benchmarks.gold_semantic_relevance for result in scenario_results) / count,
        4,
    )
    mean_gold_semantic_precision = round(
        sum(result.benchmarks.gold_semantic_precision for result in scenario_results) / count,
        4,
    )
    validation_pass_rate = round(
        sum(1 for result in scenario_results if result.validation_passed) / count,
        4,
    )
    return RagConfigScore(
        hyperparameters=hyperparameters,
        mean_phrase_coverage=mean_phrase_coverage,
        mean_first_phrase_rank_reciprocal=mean_first_phrase_rank_reciprocal,
        mean_gold_semantic_relevance=mean_gold_semantic_relevance,
        mean_gold_semantic_precision=mean_gold_semantic_precision,
        validation_pass_rate=validation_pass_rate,
        scenario_results=tuple(scenario_results),
    )


def _uses_semantic_objective(scores: list[RagConfigScore]) -> bool:
    return any(score.mean_gold_semantic_relevance > 0.0 for score in scores)


def compare_config_scores(left: RagConfigScore, right: RagConfigScore) -> int:
    """Return positive when left is better than right (primary + tie-breakers)."""
    if left.mean_gold_semantic_relevance > 0.0 or right.mean_gold_semantic_relevance > 0.0:
        if left.mean_gold_semantic_relevance != right.mean_gold_semantic_relevance:
            return _compare_float(
                left.mean_gold_semantic_relevance,
                right.mean_gold_semantic_relevance,
            )
        if left.mean_gold_semantic_precision != right.mean_gold_semantic_precision:
            return _compare_float(
                left.mean_gold_semantic_precision,
                right.mean_gold_semantic_precision,
            )
    if left.mean_phrase_coverage != right.mean_phrase_coverage:
        return _compare_float(left.mean_phrase_coverage, right.mean_phrase_coverage)
    if left.mean_first_phrase_rank_reciprocal != right.mean_first_phrase_rank_reciprocal:
        return _compare_float(
            left.mean_first_phrase_rank_reciprocal,
            right.mean_first_phrase_rank_reciprocal,
        )
    return _compare_float(left.validation_pass_rate, right.validation_pass_rate)


def select_best_config(scores: list[RagConfigScore]) -> RagConfigScore | None:
    """Pick the best configuration using deterministic tie-breaking."""
    if not scores:
        return None
    best = scores[0]
    for candidate in scores[1:]:
        if compare_config_scores(candidate, best) > 0:
            best = candidate
    return best


def _compare_float(left: float, right: float) -> int:
    if left > right:
        return 1
    if left < right:
        return -1
    return 0


def _coerce_retrieval_mode(value: object) -> RetrievalMode:
    mode = str(value)
    if mode not in ("vector", "hybrid"):
        msg = f"Invalid retrieval_mode: {value}"
        raise ValueError(msg)
    return mode  # type: ignore[return-value]


def _coerce_mode_tuple(
    value: object,
    default: tuple[RetrievalMode, ...],
) -> tuple[RetrievalMode, ...]:
    if not isinstance(value, list) or not value:
        return default
    return tuple(_coerce_retrieval_mode(item) for item in value)


def _coerce_int_tuple(value: object, default: tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        return default
    return tuple(int(item) for item in value)


def _coerce_bool_tuple(value: object, default: tuple[bool, ...]) -> tuple[bool, ...]:
    if not isinstance(value, list) or not value:
        return default
    return tuple(bool(item) for item in value)
