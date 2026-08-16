"""Calibration of grader scores vs golden human rubric (E18.3)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import NamedTuple

from mcp_server.domain.golden_project_reviews import (
    REQUIRED_GOLDEN_KEYS,
    GoldenCorpusError,
    load_golden_corpus,
    passes_delivery_review,
)


class CalibrationRow(NamedTuple):
    key: str
    expected_score: int
    observed_score: int
    abs_delta: int
    expected_passed: bool
    observed_passed: bool
    pass_mismatch: bool


class CalibrationReport(NamedTuple):
    rows: tuple[CalibrationRow, ...]
    mean_abs_delta: float
    pass_mismatch_count: int
    max_abs_delta: int


def build_calibration_report(
    observed: Mapping[str, int],
) -> CalibrationReport:
    """Compare observed grader scores to human expected_score on the golden set."""
    corpus = load_golden_corpus()
    missing = [key for key in REQUIRED_GOLDEN_KEYS if key not in observed]
    if missing:
        raise GoldenCorpusError(f"missing golden key: {missing[0]}")
    rows: list[CalibrationRow] = []
    for key in REQUIRED_GOLDEN_KEYS:
        golden = corpus[key]
        observed_score = int(observed[key])
        delta = abs(observed_score - golden.expected_score)
        expected_passed = golden.expect_passed
        observed_passed = passes_delivery_review(observed_score)
        rows.append(
            CalibrationRow(
                key=key,
                expected_score=golden.expected_score,
                observed_score=observed_score,
                abs_delta=delta,
                expected_passed=expected_passed,
                observed_passed=observed_passed,
                pass_mismatch=expected_passed != observed_passed,
            )
        )
    deltas = [row.abs_delta for row in rows]
    return CalibrationReport(
        rows=tuple(rows),
        mean_abs_delta=sum(deltas) / len(deltas),
        pass_mismatch_count=sum(1 for row in rows if row.pass_mismatch),
        max_abs_delta=max(deltas),
    )


def format_calibration_markdown(report: CalibrationReport) -> str:
    lines = [
        "# Reviewer calibration vs golden rubric",
        "",
        f"- mean abs delta: {report.mean_abs_delta:.2f}",
        f"- max abs delta: {report.max_abs_delta}",
        f"- pass/fail mismatches: {report.pass_mismatch_count}",
        "",
        "| key | expected | observed | abs delta | pass mismatch |",
        "|-----|----------|----------|-----------|---------------|",
    ]
    for row in report.rows:
        lines.append(
            f"| {row.key} | {row.expected_score} | {row.observed_score} | "
            f"{row.abs_delta} | {row.pass_mismatch} |"
        )
    lines.append("")
    return "\n".join(lines)


def observed_from_human_rubric() -> dict[str, int]:
    """Baseline: grader matches human expected_score (zero drift)."""
    return {key: row.expected_score for key, row in load_golden_corpus().items()}
