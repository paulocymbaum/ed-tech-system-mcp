"""Golden project-review corpus (E18.1) — no live grader."""

from __future__ import annotations

import threading

from mcp_server.domain.golden_project_reviews import (
    GOLDEN_LABELS,
    REQUIRED_GOLDEN_KEYS,
    GoldenCorpusError,
    assert_expected_comments_valid,
    empty_content_fail,
    get_golden,
    load_golden_corpus,
    passes_delivery_review,
    require_complete_corpus,
)
from mcp_server.domain.project_review import validate_review_comment
from mcp_server.domain.socratic import SUPPORTED_LOCALES


def test_corpus_has_twelve_locale_label_keys() -> None:
    corpus = load_golden_corpus()
    require_complete_corpus(corpus)
    assert len(corpus) == 12
    assert set(corpus) == set(REQUIRED_GOLDEN_KEYS)
    for locale in SUPPORTED_LOCALES:
        for label in GOLDEN_LABELS:
            row = get_golden(locale, label)
            assert row.locale == locale
            assert row.label == label


def test_pass_and_fail_bands_match_threshold() -> None:
    passed = get_golden("en", "pass")
    failed = get_golden("en", "fail")
    assert passed.expected_score > 80
    assert passed.expect_passed is True
    assert failed.expected_score <= 80
    assert failed.expect_passed is False
    assert passes_delivery_review(80) is False
    assert passes_delivery_review(81) is True


def test_expected_comments_pass_validator() -> None:
    assert_expected_comments_valid()


def test_missing_locale_file_fails_closed() -> None:
    corpus = dict(load_golden_corpus())
    del corpus["zh/fail"]
    try:
        require_complete_corpus(corpus)
    except GoldenCorpusError as exc:
        assert "zh/fail" in str(exc)
    else:
        raise AssertionError("expected GoldenCorpusError")


def test_banned_jargon_comment_rejected() -> None:
    result = validate_review_comment(
        "Looks fine but project-delivery.json was not updated."
    )
    assert result["ok"] is False


def test_borderline_band_and_exclusive_pass() -> None:
    row = get_golden("en", "borderline")
    assert row.expected_score_min == 78
    assert row.expected_score_max == 82
    assert 78 <= row.expected_score <= 82
    assert row.expect_passed is passes_delivery_review(row.expected_score)


def test_locale_normalization_fallback() -> None:
    assert get_golden("EN", "pass").locale == "en"
    assert get_golden("pt-BR", "fail").locale == "pt"


def test_empty_delivery_content_is_fail_not_pass() -> None:
    row = empty_content_fail(locale="en")
    assert row.content == ""
    assert row.expect_passed is False
    assert row.label == "fail"


def test_parallel_corpus_loads_are_identical() -> None:
    snapshots: list[set[str]] = []

    def worker() -> None:
        snapshots.append(set(load_golden_corpus()))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert snapshots
    first = snapshots[0]
    assert all(item == first for item in snapshots)
