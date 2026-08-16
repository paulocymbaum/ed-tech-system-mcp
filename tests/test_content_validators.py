"""Tests for EdHarness content validators (E6.4)."""

from __future__ import annotations

from mcp_server.domain.content_validators import (
    validate_lesson_bundle,
    validate_project_readme,
    validate_project_tests_json,
    validate_quiz_payload,
)


def test_validate_quiz_accepts_harness_shape() -> None:
    quiz = {
        "id": "quiz",
        "title": "Check",
        "questions": [
            {
                "id": "q1",
                "prompt": "Pick one",
                "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "correctOptionId": "a",
            }
        ],
    }
    report = validate_quiz_payload(quiz)
    assert report.ok


def test_validate_quiz_rejects_missing_correct_option() -> None:
    quiz = {
        "id": "quiz",
        "title": "Check",
        "questions": [
            {
                "id": "q1",
                "prompt": "Pick one",
                "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                "correctOptionId": "z",
            }
        ],
    }
    report = validate_quiz_payload(quiz)
    assert not report.ok


def test_validate_project_readme_requires_sections() -> None:
    report = validate_project_readme("# Title\n\n## Goal\n\nx")
    assert not report.ok


def test_validate_project_tests_json_requires_cases() -> None:
    report = validate_project_tests_json('{"cases": []}')
    assert not report.ok


def test_validate_lesson_bundle_readme_and_meta() -> None:
    report = validate_lesson_bundle(
        readme_markdown="# Lesson\n\nBody content here.",
        meta={
            "id": "01.1-lesson",
            "graphIndex": "01.1",
            "graphNodeId": "n_abc",
            "title": "Lesson",
        },
    )
    assert report.ok
