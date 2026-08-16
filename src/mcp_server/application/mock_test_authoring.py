"""Mock-test structure builder for EF2 import bundles (E9.2)."""

from __future__ import annotations

from mcp_server.domain.authoring import (
    MOCK_SECTION_TYPES,
    MockTestBundleEntry,
    MockTestSectionSpec,
    MockTestStructureResult,
)
from mcp_server.domain.content_validators import validate_mock_test_bundle


def default_mock_module_slug(study_module_slug: str) -> str:
    slug = study_module_slug.strip()
    if slug.endswith("-mock"):
        return slug
    return f"{slug}-mock"


def default_section_lesson_slugs(study_module_slug: str) -> tuple[str, str, str]:
    """Return lesson slug stems for the three standard sections."""
    prefix = study_module_slug.split("-", 1)[0] if study_module_slug else "01"
    return (
        f"{prefix}.1-test-instructions",
        f"{prefix}.2-multiple-choice",
        f"{prefix}.3-coding-challenge",
    )


def build_mock_test_structure(
    *,
    study_module_slug: str,
    mock_module_slug: str | None = None,
    duration_minutes: int = 90,
    passing_score_percent: int = 70,
    instructions_lesson_slug: str | None = None,
    quiz_lesson_slug: str | None = None,
    coding_lesson_slug: str | None = None,
) -> MockTestStructureResult:
    """Build a three-section mock test payload compatible with EF2 ``mock_tests``."""
    module_slug = mock_module_slug or default_mock_module_slug(study_module_slug)
    default_slugs = default_section_lesson_slugs(study_module_slug)
    sections = [
        MockTestSectionSpec(
            lesson_slug=instructions_lesson_slug or default_slugs[0],
            position=1,
            section_type="instructions",
            module_slug=module_slug,
        ),
        MockTestSectionSpec(
            lesson_slug=quiz_lesson_slug or default_slugs[1],
            position=2,
            section_type="quiz",
            module_slug=module_slug,
        ),
        MockTestSectionSpec(
            lesson_slug=coding_lesson_slug or default_slugs[2],
            position=3,
            section_type="coding",
            module_slug=module_slug,
        ),
    ]
    mock_test = MockTestBundleEntry(
        module_slug=module_slug,
        duration_minutes=duration_minutes,
        passing_score_percent=passing_score_percent,
        sections=sections,
    )
    report = validate_mock_test_bundle(mock_test.model_dump())
    messages = [f"[{f.level}] {f.message}" for f in report.findings]
    ef2_fragment = {
        "mock_tests": [mock_test.model_dump()],
        "lessons_hint": [
            {
                "module_slug": module_slug,
                "slug": s.lesson_slug,
                "title": _section_title(s.section_type),
                "mock_section": s.section_type,
                "graph_index": f"{study_module_slug.split('-', 1)[0]}.{s.position}",
            }
            for s in sections
        ],
        "section_order": list(MOCK_SECTION_TYPES),
    }
    return MockTestStructureResult(
        mock_test=mock_test,
        ef2_fragment=ef2_fragment,
        validation_ok=report.ok,
        validation_messages=messages,
    )


def _section_title(section_type: str) -> str:
    titles = {
        "instructions": "Test Instructions",
        "quiz": "Multiple Choice",
        "coding": "Coding Challenge",
    }
    return titles.get(section_type, section_type.title())
