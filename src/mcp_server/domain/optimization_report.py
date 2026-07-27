"""Pure types and scoring for RAG hyperparameter optimization reports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from mcp_server.domain.rag_hyperparameters import RagHyperparameters

_NO_ANSWER_MARKER = "NO_ANSWER_IN_CORPUS"
_QUOTED_TITLE_PATTERN = re.compile(r"'([^']{15,})'")


def derive_expected_phrases_from_chunk_texts(
    chunk_texts: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Derive phrase anchors from labeled relevant corpus chunks.

    The bundled test-dataset gold answers are abstractive summaries that do not
    appear verbatim in chunk text. Relevant chunks instead carry distinctive
    quoted document titles that survive re-chunking during validation runs.
    """
    segments: list[str] = []
    for text in chunk_texts:
        for match in _QUOTED_TITLE_PATTERN.findall(text):
            segment = match.strip()
            if len(segment) >= 15:
                segments.append(segment)

    if not segments:
        return ()

    seen: set[str] = set()
    unique: list[str] = []
    for segment in segments:
        key = segment.lower()
        if key not in seen:
            seen.add(key)
            unique.append(segment)
    return tuple(unique[:6])


def filter_phrases_present_in_document(
    phrases: tuple[str, ...] | list[str],
    document_text: str,
) -> tuple[str, ...]:
    """Keep only phrases that appear verbatim in the assembled document body."""
    haystack = document_text.lower()
    kept: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        normalized = phrase.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        if key in haystack:
            seen.add(key)
            kept.append(normalized)
    return tuple(kept)


def derive_expected_phrases_from_gold_answer(gold_answer: str) -> tuple[str, ...]:
    """Derive retrieval phrases from a gold answer using document-honest clause splitting."""
    text = gold_answer.strip()
    if not text or text == _NO_ANSWER_MARKER:
        return ()

    segments: list[str] = []
    for sentence in re.split(r"[.!?]+", text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if "," in sentence:
            for clause in sentence.split(","):
                clause = clause.strip()
                if len(clause) >= 3:
                    segments.append(clause)
        elif len(sentence) >= 3:
            segments.append(sentence)

    if not segments:
        segments = [text]

    seen: set[str] = set()
    unique: list[str] = []
    for segment in segments:
        key = segment.lower()
        if key not in seen:
            seen.add(key)
            unique.append(segment)
    return tuple(unique[:6])


@dataclass(frozen=True, slots=True)
class ScenarioOptimizationRow:
    """Per-scenario benchmark summary for one optimization phase."""

    scenario_name: str
    query: str
    phrase_coverage: float
    first_phrase_rank_reciprocal: float
    gold_semantic_relevance: float
    gold_semantic_precision: float
    validation_passed: bool

    def as_dict(self) -> dict[str, str | float | bool]:
        return {
            "scenario_name": self.scenario_name,
            "query": self.query,
            "phrase_coverage": self.phrase_coverage,
            "first_phrase_rank_reciprocal": self.first_phrase_rank_reciprocal,
            "gold_semantic_relevance": self.gold_semantic_relevance,
            "gold_semantic_precision": self.gold_semantic_precision,
            "validation_passed": self.validation_passed,
        }


@dataclass(frozen=True, slots=True)
class OptimizationPhaseResult:
    """Aggregate benchmark outcome for a single hyperparameter configuration."""

    hyperparameters: RagHyperparameters
    mean_phrase_coverage: float
    mean_first_phrase_rank_reciprocal: float
    mean_gold_semantic_relevance: float
    mean_gold_semantic_precision: float
    validation_pass_rate: float
    scenarios: tuple[ScenarioOptimizationRow, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "hyperparameters": self.hyperparameters.as_dict(),
            "mean_phrase_coverage": self.mean_phrase_coverage,
            "mean_first_phrase_rank_reciprocal": self.mean_first_phrase_rank_reciprocal,
            "mean_gold_semantic_relevance": self.mean_gold_semantic_relevance,
            "mean_gold_semantic_precision": self.mean_gold_semantic_precision,
            "validation_pass_rate": self.validation_pass_rate,
            "scenarios": [row.as_dict() for row in self.scenarios],
        }


@dataclass(frozen=True, slots=True)
class OptimizationDiff:
    """Before/after deltas for headline optimization metrics."""

    mean_phrase_coverage_delta: float
    mean_first_phrase_rank_reciprocal_delta: float
    mean_gold_semantic_relevance_delta: float
    mean_gold_semantic_precision_delta: float
    validation_pass_rate_delta: float

    def as_dict(self) -> dict[str, float]:
        return {
            "mean_phrase_coverage_delta": self.mean_phrase_coverage_delta,
            "mean_first_phrase_rank_reciprocal_delta": self.mean_first_phrase_rank_reciprocal_delta,
            "mean_gold_semantic_relevance_delta": self.mean_gold_semantic_relevance_delta,
            "mean_gold_semantic_precision_delta": self.mean_gold_semantic_precision_delta,
            "validation_pass_rate_delta": self.validation_pass_rate_delta,
        }


@dataclass(frozen=True, slots=True)
class RagOptimizationReport:
    """Persisted before/after optimization report."""

    created_at: str
    scenario_count: int
    before: OptimizationPhaseResult
    after: OptimizationPhaseResult
    diff: OptimizationDiff
    optimized_at: str
    objective: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "created_at": self.created_at,
            "scenario_count": self.scenario_count,
            "before": self.before.as_dict(),
            "after": self.after.as_dict(),
            "diff": self.diff.as_dict(),
            "optimized_at": self.optimized_at,
            "objective": self.objective,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RagOptimizationReport:
        before_raw = payload["before"]
        after_raw = payload["after"]
        diff_raw = payload["diff"]
        if not isinstance(before_raw, dict) or not isinstance(after_raw, dict):
            msg = "Optimization report before/after must be objects"
            raise ValueError(msg)
        if not isinstance(diff_raw, dict):
            msg = "Optimization report diff must be an object"
            raise ValueError(msg)
        return cls(
            created_at=str(payload["created_at"]),
            scenario_count=int(payload["scenario_count"]),
            before=_phase_from_dict(before_raw),
            after=_phase_from_dict(after_raw),
            diff=OptimizationDiff(
                mean_phrase_coverage_delta=float(diff_raw["mean_phrase_coverage_delta"]),
                mean_first_phrase_rank_reciprocal_delta=float(
                    diff_raw["mean_first_phrase_rank_reciprocal_delta"]
                ),
                mean_gold_semantic_relevance_delta=float(
                    diff_raw.get("mean_gold_semantic_relevance_delta", 0.0)
                ),
                mean_gold_semantic_precision_delta=float(
                    diff_raw.get("mean_gold_semantic_precision_delta", 0.0)
                ),
                validation_pass_rate_delta=float(diff_raw["validation_pass_rate_delta"]),
            ),
            optimized_at=str(payload["optimized_at"]),
            objective=str(payload.get("objective", "mean_phrase_coverage")),
        )


def compute_optimization_diff(
    before: OptimizationPhaseResult,
    after: OptimizationPhaseResult,
) -> OptimizationDiff:
    """Compute headline metric deltas between before and after phases."""
    return OptimizationDiff(
        mean_phrase_coverage_delta=round(
            after.mean_phrase_coverage - before.mean_phrase_coverage,
            4,
        ),
        mean_first_phrase_rank_reciprocal_delta=round(
            after.mean_first_phrase_rank_reciprocal - before.mean_first_phrase_rank_reciprocal,
            4,
        ),
        mean_gold_semantic_relevance_delta=round(
            after.mean_gold_semantic_relevance - before.mean_gold_semantic_relevance,
            4,
        ),
        mean_gold_semantic_precision_delta=round(
            after.mean_gold_semantic_precision - before.mean_gold_semantic_precision,
            4,
        ),
        validation_pass_rate_delta=round(
            after.validation_pass_rate - before.validation_pass_rate,
            4,
        ),
    )


def build_optimization_report(
    *,
    created_at: str,
    optimized_at: str,
    before: OptimizationPhaseResult,
    after: OptimizationPhaseResult,
    objective: str = "mean_phrase_coverage",
) -> RagOptimizationReport:
    """Assemble a before/after optimization report with computed diffs."""
    return RagOptimizationReport(
        created_at=created_at,
        scenario_count=len(before.scenarios),
        before=before,
        after=after,
        diff=compute_optimization_diff(before, after),
        optimized_at=optimized_at,
        objective=objective,
    )


def _phase_from_dict(payload: dict[str, Any]) -> OptimizationPhaseResult:
    scenarios_raw = payload.get("scenarios", [])
    scenarios: list[ScenarioOptimizationRow] = []
    if isinstance(scenarios_raw, list):
        for item in scenarios_raw:
            if not isinstance(item, dict):
                continue
            scenarios.append(
                ScenarioOptimizationRow(
                    scenario_name=str(item["scenario_name"]),
                    query=str(item.get("query", "")),
                    phrase_coverage=float(item["phrase_coverage"]),
                    first_phrase_rank_reciprocal=float(item["first_phrase_rank_reciprocal"]),
                    gold_semantic_relevance=float(item.get("gold_semantic_relevance", 0.0)),
                    gold_semantic_precision=float(item.get("gold_semantic_precision", 0.0)),
                    validation_passed=bool(item["validation_passed"]),
                )
            )
    return OptimizationPhaseResult(
        hyperparameters=RagHyperparameters.from_dict(payload["hyperparameters"]),
        mean_phrase_coverage=float(payload["mean_phrase_coverage"]),
        mean_first_phrase_rank_reciprocal=float(payload["mean_first_phrase_rank_reciprocal"]),
        mean_gold_semantic_relevance=float(payload.get("mean_gold_semantic_relevance", 0.0)),
        mean_gold_semantic_precision=float(payload.get("mean_gold_semantic_precision", 0.0)),
        validation_pass_rate=float(payload["validation_pass_rate"]),
        scenarios=tuple(scenarios),
    )
