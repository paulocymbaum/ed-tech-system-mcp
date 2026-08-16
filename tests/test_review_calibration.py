"""E18.3 calibration report vs golden expected scores."""

from mcp_server.domain.golden_project_reviews import GoldenCorpusError
from mcp_server.domain.review_calibration import (
    build_calibration_report,
    format_calibration_markdown,
    observed_from_human_rubric,
)


def test_human_rubric_baseline_has_zero_drift() -> None:
    report = build_calibration_report(observed_from_human_rubric())
    assert report.mean_abs_delta == 0
    assert report.pass_mismatch_count == 0
    markdown = format_calibration_markdown(report)
    assert "en/pass" in markdown
    assert "pass/fail mismatches: 0" in markdown


def test_missing_observed_key_fails_closed() -> None:
    observed = observed_from_human_rubric()
    del observed["zh/fail"]
    try:
        build_calibration_report(observed)
    except GoldenCorpusError as exc:
        assert "zh/fail" in str(exc)
    else:
        raise AssertionError("expected GoldenCorpusError")


def test_pass_mismatch_when_grader_crosses_threshold() -> None:
    observed = observed_from_human_rubric()
    observed["en/fail"] = 81
    report = build_calibration_report(observed)
    fail_row = next(row for row in report.rows if row.key == "en/fail")
    assert fail_row.pass_mismatch is True
    assert report.pass_mismatch_count >= 1
