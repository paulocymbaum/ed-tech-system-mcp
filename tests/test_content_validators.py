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


def test_validate_project_dict_repairs_invalid_tests_json() -> None:
    from mcp_server.application.authoring_service import validate_project_dict

    project = {
        "readme_markdown": (
            "# Title\n## Problem context\nx\n## Goal\ny\n"
            "## Lesson concepts practiced\nz\n## Functional requirements\na\n"
            "## Non-functional requirements\nb\n## Constraints\nc\n"
            "## Acceptance criteria\nd\n## Suggested plan\ne\nstarter/\n"
        ),
        "files": [
            {
                "path": "starter/tests.json",
                "kind": "starter",
                # Unescaped quotes — common LLM failure mode.
                "content": (
                    '[{"id":"t1","name":"x","stdin":"11, ["doctor\'s note"]",'
                    '"expectedStdout":"Eligible"}]'
                ),
            }
        ],
        "test_cases": [
            {
                "id": "t1",
                "name": "x",
                "stdin": '11, ["doctor\'s note"]',
                "expectedStdout": "Eligible",
            }
        ],
    }
    findings = validate_project_dict(project, strict_readme_sections=False)
    assert not any(f.startswith("error:") for f in findings)
    assert any("repaired from structured test_cases" in f for f in findings)
    import json

    json.loads(project["files"][0]["content"])
