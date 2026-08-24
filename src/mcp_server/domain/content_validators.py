"""Python validators ported from PraxisWeb validate-*.mjs (E6.4)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from mcp_server.domain.curriculum_enums import (
    LESSON_STACKS,
    MOCK_SECTION_TYPES,
    PROJECT_FILE_KINDS,
    RUN_DEPENDENCY_KINDS,
    RUNNER_KINDS,
    normalize_project_file_kind,
)

LESSON_CONCEPTS_SECTION = "Lesson concepts practiced"

# Re-export for callers / tests that imported from this module.
KNOWN_LESSON_STACKS = LESSON_STACKS
KNOWN_RUNNER_KINDS = RUNNER_KINDS
KNOWN_RUN_DEPENDENCY_KINDS = RUN_DEPENDENCY_KINDS
KNOWN_PROJECT_FILE_KINDS = PROJECT_FILE_KINDS

REQUIRED_PBL_SECTIONS = [
    "Problem context",
    "Goal",
    LESSON_CONCEPTS_SECTION,
    "Functional requirements",
    "Non-functional requirements",
    "Constraints",
    "Acceptance criteria",
    "Suggested plan",
    "Deliverables",
]


@dataclass
class ValidationFinding:
    level: str  # "error" | "warn"
    message: str
    path: str = "."


@dataclass
class ValidationReport:
    findings: list[ValidationFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[ValidationFinding]:
        return [f for f in self.findings if f.level == "warn"]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def _escape_regexp(value: str) -> str:
    return re.escape(value)


def _has_section(markdown: str, title: str) -> bool:
    pattern = re.compile(rf"^##\s+{_escape_regexp(title)}", re.IGNORECASE | re.MULTILINE)
    if pattern.search(markdown):
        return True
    if title == "Example data":
        return bool(
            re.search(
                r"^##\s+Example data(\s+\(if applicable\))?", markdown, re.IGNORECASE | re.MULTILINE
            )
        )
    if title == "Suggested plan":
        return bool(
            re.search(
                r"^##\s+Suggested plan(\s+\(no solution\))?", markdown, re.IGNORECASE | re.MULTILINE
            )
        )
    if title == "Extensions":
        return bool(
            re.search(r"^##\s+Extensions(\s+\(optional\))?", markdown, re.IGNORECASE | re.MULTILINE)
        )
    if title == LESSON_CONCEPTS_SECTION:
        return bool(
            re.search(r"^##\s+Lesson concepts practiced", markdown, re.IGNORECASE | re.MULTILINE)
        )
    return False


def _extract_section_body(markdown: str, heading: str) -> str:
    pattern = re.compile(
        rf"(^|\r?\n)##\s+{_escape_regexp(heading)}\s*\r?\n([\s\S]*)",
        re.IGNORECASE,
    )
    match = pattern.search(markdown)
    if not match:
        return ""
    body = match.group(2)
    next_heading = re.search(r"\r?\n##\s", body)
    return body[: next_heading.start()] if next_heading else body


def _count_lesson_concept_items(markdown: str) -> int:
    section = _extract_section_body(markdown, LESSON_CONCEPTS_SECTION)
    if not section:
        return 0
    return len(re.findall(r"^-\s+\[\s*\]\s+", section, re.MULTILINE))


def validate_quiz_payload(value: Any, *, file_label: str = "") -> ValidationReport:
    """Validate quiz JSON (PraxisWeb validate-quiz.mjs rules)."""
    report = ValidationReport()
    if not isinstance(value, dict):
        report.findings.append(ValidationFinding("error", "Root must be a JSON object."))
        return report

    if not isinstance(value.get("id"), str) or not str(value["id"]).strip():
        report.findings.append(ValidationFinding("error", "`id` must be a non-empty string."))
    if not isinstance(value.get("title"), str) or not str(value["title"]).strip():
        report.findings.append(ValidationFinding("error", "`title` must be a non-empty string."))
    if value.get("description") is not None and not isinstance(value["description"], str):
        report.findings.append(
            ValidationFinding("error", "`description` must be a string when present.")
        )
    if value.get("lessonId") is not None and not isinstance(value["lessonId"], str):
        report.findings.append(
            ValidationFinding("error", "`lessonId` must be a string when present.")
        )
    if value.get("graphIndex") is not None and not isinstance(value["graphIndex"], str):
        report.findings.append(
            ValidationFinding("error", "`graphIndex` must be a string when present.")
        )

    questions = value.get("questions")
    if not isinstance(questions, list) or len(questions) == 0:
        report.findings.append(ValidationFinding("error", "`questions` must be a non-empty array."))
        return report

    question_ids: set[str] = set()
    for index, question in enumerate(questions):
        label = f"questions[{index}]"
        if not isinstance(question, dict):
            report.findings.append(ValidationFinding("error", f"{label}: must be an object."))
            continue
        qid = question.get("id")
        if not isinstance(qid, str) or not qid.strip():
            report.findings.append(
                ValidationFinding("error", f"{label}: `id` must be a non-empty string.")
            )
        elif qid in question_ids:
            report.findings.append(
                ValidationFinding("error", f'{label}: duplicate question id "{qid}".')
            )
        else:
            question_ids.add(qid)

        if not isinstance(question.get("prompt"), str) or not str(question["prompt"]).strip():
            report.findings.append(
                ValidationFinding("error", f"{label}: `prompt` must be a non-empty string.")
            )

        correct = question.get("correctOptionId")
        if not isinstance(correct, str) or not correct.strip():
            report.findings.append(
                ValidationFinding(
                    "error", f"{label}: `correctOptionId` must be a non-empty string."
                )
            )

        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4:
            report.findings.append(
                ValidationFinding(
                    "error", f"{label}: `options` must contain exactly 4 entries."
                )
            )
            continue

        option_ids: set[str] = set()
        for o_index, option in enumerate(options):
            o_label = f"{label}.options[{o_index}]"
            if not isinstance(option, dict):
                report.findings.append(ValidationFinding("error", f"{o_label}: must be an object."))
                continue
            oid = option.get("id")
            if not isinstance(oid, str) or not oid.strip():
                report.findings.append(
                    ValidationFinding("error", f"{o_label}: `id` must be a non-empty string.")
                )
            elif oid in option_ids:
                report.findings.append(
                    ValidationFinding("error", f'{o_label}: duplicate option id "{oid}".')
                )
            else:
                option_ids.add(oid)
            if not isinstance(option.get("text"), str) or not str(option["text"]).strip():
                report.findings.append(
                    ValidationFinding("error", f"{o_label}: `text` must be a non-empty string.")
                )

        if isinstance(correct, str) and correct and correct not in option_ids:
            report.findings.append(
                ValidationFinding(
                    "error",
                    f'{label}: `correctOptionId` "{correct}" does not match any option id.',
                )
            )

    if file_label and isinstance(value.get("id"), str):
        import os

        base = os.path.splitext(os.path.basename(file_label))[0]
        if value["id"] != base and not base.endswith(value["id"]):
            report.findings.append(
                ValidationFinding(
                    "warn",
                    f'Hint: file name "{base}.json" usually matches quiz id "{value["id"]}".',
                )
            )

    return report


def validate_project_readme(
    markdown: str, *, required_sections_as_errors: bool = True
) -> ValidationReport:
    """Validate project README.md (PraxisWeb project-contract.mjs)."""
    report = ValidationReport()
    if not markdown.strip():
        report.findings.append(ValidationFinding("error", "README.md is empty"))
        return report
    if not re.search(r"^#\s+.+", markdown, re.MULTILINE):
        report.findings.append(ValidationFinding("error", "Missing top-level # title"))
    section_level = "error" if required_sections_as_errors else "warn"
    for section in REQUIRED_PBL_SECTIONS:
        if not _has_section(markdown, section):
            # Author pipeline passes required_sections_as_errors=False so LLM first
            # drafts can still save; standalone validate_project stays strict.
            report.findings.append(
                ValidationFinding(section_level, f"Missing section: ## {section}")
            )
    if not _has_section(markdown, "Example data"):
        report.findings.append(
            ValidationFinding("warn", "Missing optional section: ## Example data (if applicable)")
        )
    if not re.search(r"\bstarter/", markdown, re.IGNORECASE):
        report.findings.append(ValidationFinding("warn", "Deliverables should mention starter/"))
    if not re.search(r"\btests\.json\b", markdown, re.IGNORECASE) and not re.search(
        r"test cases", markdown, re.IGNORECASE
    ):
        report.findings.append(
            ValidationFinding(
                "warn", "Deliverables should mention starter/tests.json validation cases"
            )
        )
    return report


def validate_project_tests_json(raw: str) -> ValidationReport:
    """Validate starter/tests.json content."""
    report = ValidationReport()
    if not raw.strip():
        report.findings.append(ValidationFinding("error", "starter/tests.json is empty"))
        return report
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        report.findings.append(ValidationFinding("error", "starter/tests.json is not valid JSON"))
        return report

    cases = (
        parsed
        if isinstance(parsed, list)
        else parsed.get("cases")
        if isinstance(parsed, dict)
        else None
    )
    if not isinstance(cases, list) or len(cases) == 0:
        report.findings.append(
            ValidationFinding("error", "starter/tests.json must define a non-empty cases array")
        )
        return report

    scored = 0
    for index, item in enumerate(cases):
        if not isinstance(item, dict):
            report.findings.append(
                ValidationFinding("error", f"starter/tests.json cases[{index}] must be an object")
            )
            continue
        if not isinstance(item.get("stdin"), str):
            report.findings.append(
                ValidationFinding(
                    "error", f"starter/tests.json cases[{index}] missing string stdin"
                )
            )
        if isinstance(item.get("expectedStdout"), str) or isinstance(
            item.get("expectedExitCode"), int
        ):
            scored += 1
    if scored == 0:
        report.findings.append(
            ValidationFinding(
                "warn",
                "starter/tests.json has no scored cases "
                "(add expectedStdout or expectedExitCode for Pass/Fail)",
            )
        )
    return report


def validate_lesson_meta(meta: Any) -> ValidationReport:
    """Validate lesson.meta.json required fields."""
    report = ValidationReport()
    if not isinstance(meta, dict):
        report.findings.append(ValidationFinding("error", "lesson.meta.json missing or invalid"))
        return report
    for field_name in ("id", "graphIndex", "graphNodeId", "title"):
        if not meta.get(field_name):
            report.findings.append(
                ValidationFinding(
                    "error",
                    f"lesson.meta.json missing required field: {field_name}",
                )
            )
    if meta.get("description") is not None and not isinstance(meta["description"], str):
        report.findings.append(
            ValidationFinding("error", "lesson.meta.json description must be a string when present")
        )
    deps = meta.get("lesson_dependencies")
    if deps is not None:
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            report.findings.append(
                ValidationFinding(
                    "error", "lesson.meta.json lesson_dependencies must be an array of strings"
                )
            )
    return report


def validate_lesson_bundle(
    *,
    readme_markdown: str,
    meta: Any,
    quiz: Any | None = None,
    project_readme: str | None = None,
    project_tests_json: str | None = None,
    strict_project_readme_sections: bool = True,
) -> ValidationReport:
    """Validate lesson README + meta (+ optional nested quiz/project)."""
    report = ValidationReport()
    if not readme_markdown.strip():
        report.findings.append(ValidationFinding("error", "README.md missing or empty"))
    meta_report = validate_lesson_meta(meta)
    report.findings.extend(meta_report.findings)
    if quiz is not None:
        quiz_report = validate_quiz_payload(quiz)
        report.findings.extend(quiz_report.findings)
    if project_readme is not None:
        readme_report = validate_project_readme(
            project_readme,
            required_sections_as_errors=strict_project_readme_sections,
        )
        report.findings.extend(readme_report.findings)
    if project_tests_json is not None:
        tests_report = validate_project_tests_json(project_tests_json)
        report.findings.extend(tests_report.findings)
    return report



def validate_mock_test_bundle(value: Any) -> ValidationReport:
    """Validate EF2 ``mock_tests[]`` entry (three ordered sections)."""
    report = ValidationReport()
    if not isinstance(value, dict):
        report.findings.append(ValidationFinding("error", "mock_test must be a JSON object"))
        return report

    module_slug = value.get("module_slug")
    if not isinstance(module_slug, str) or not module_slug.strip():
        report.findings.append(
            ValidationFinding("error", "`module_slug` must be a non-empty string")
        )
    elif not str(module_slug).endswith("-mock"):
        report.findings.append(
            ValidationFinding("warn", "`module_slug` should end with `-mock` for mock modules")
        )

    duration = value.get("duration_minutes")
    if not isinstance(duration, int) or duration < 1:
        report.findings.append(
            ValidationFinding("error", "`duration_minutes` must be a positive integer")
        )

    passing = value.get("passing_score_percent")
    if not isinstance(passing, int) or passing < 0 or passing > 100:
        report.findings.append(
            ValidationFinding("error", "`passing_score_percent` must be an integer 0–100")
        )

    sections = value.get("sections")
    if not isinstance(sections, list):
        report.findings.append(ValidationFinding("error", "`sections` must be an array"))
        return report
    if len(sections) != 3:
        report.findings.append(
            ValidationFinding("error", "`sections` must contain exactly 3 items")
        )

    positions: set[int] = set()
    lesson_slugs: set[str] = set()
    typed_sections: list[tuple[int, str]] = []
    for index, section in enumerate(sections):
        path = f"sections[{index}]"
        if not isinstance(section, dict):
            report.findings.append(ValidationFinding("error", f"{path} must be an object"))
            continue
        lesson_slug = section.get("lesson_slug")
        if not isinstance(lesson_slug, str) or not lesson_slug.strip():
            report.findings.append(
                ValidationFinding("error", f"{path}.lesson_slug must be a non-empty string")
            )
        elif lesson_slug in lesson_slugs:
            report.findings.append(
                ValidationFinding("error", f"duplicate lesson_slug `{lesson_slug}`")
            )
        else:
            lesson_slugs.add(lesson_slug)

        position = section.get("position")
        if not isinstance(position, int) or position < 1 or position > 3:
            report.findings.append(
                ValidationFinding("error", f"{path}.position must be 1, 2, or 3")
            )
        elif position in positions:
            report.findings.append(
                ValidationFinding("error", f"duplicate section position `{position}`")
            )
        else:
            positions.add(position)

        section_type = section.get("section_type")
        if section_type not in MOCK_SECTION_TYPES:
            report.findings.append(
                ValidationFinding(
                    "error",
                    f"{path}.section_type must be one of: {', '.join(sorted(MOCK_SECTION_TYPES))}",
                )
            )
        else:
            typed_sections.append((int(position), str(section_type)))

    types_seen = [t for _, t in sorted(typed_sections, key=lambda item: item[0])]
    if types_seen != ["instructions", "quiz", "coding"]:
        report.findings.append(
            ValidationFinding(
                "error",
                "sections must appear in order: instructions (1), quiz (2), coding (3)",
            )
        )
    return report


def validate_run_dependencies(deps: Any) -> ValidationReport:
    """Validate ``run_dependencies`` kinds against curriculum CHECK + FE usage."""
    report = ValidationReport()
    if deps is None:
        return report
    if not isinstance(deps, list):
        report.findings.append(
            ValidationFinding("error", "run_dependencies must be an array")
        )
        return report
    for index, item in enumerate(deps):
        if not isinstance(item, dict):
            report.findings.append(
                ValidationFinding("error", f"run_dependencies[{index}] must be an object")
            )
            continue
        kind = item.get("kind")
        if kind is None:
            continue  # SQL defaults missing kind to npm
        if str(kind) not in RUN_DEPENDENCY_KINDS:
            report.findings.append(
                ValidationFinding(
                    "error",
                    f"run_dependencies[{index}].kind `{kind}` invalid "
                    f"(allowed: {', '.join(sorted(RUN_DEPENDENCY_KINDS))})",
                )
            )
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            report.findings.append(
                ValidationFinding(
                    "error", f"run_dependencies[{index}].name must be a non-empty string"
                )
            )
    return report


def validate_lesson_stack(stack: Any) -> ValidationReport:
    report = ValidationReport()
    if stack is None:
        return report
    if str(stack) not in LESSON_STACKS:
        report.findings.append(
            ValidationFinding(
                "error",
                f"unknown stack `{stack}` (allowed: {', '.join(sorted(LESSON_STACKS))})",
            )
        )
    return report


def validate_project_files_for_rpc(files: Any) -> ValidationReport:
    """Ensure each file kind maps to PraxisWeb/backend ``dir``|``file``."""
    report = ValidationReport()
    if files is None:
        return report
    if not isinstance(files, list):
        report.findings.append(ValidationFinding("error", "project.files must be an array"))
        return report
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            report.findings.append(
                ValidationFinding("error", f"project.files[{index}] must be an object")
            )
            continue
        path = str(item.get("path") or "")
        mapped = normalize_project_file_kind(
            item.get("kind"), path=path, content=item.get("content")
        )
        if mapped not in PROJECT_FILE_KINDS:
            report.findings.append(
                ValidationFinding(
                    "error",
                    f"project.files[{index}].kind maps to `{mapped}` "
                    f"(allowed: {', '.join(sorted(PROJECT_FILE_KINDS))})",
                )
            )
    return report


def validate_test_boilerplate(value: Any) -> ValidationReport:
    """Require LEARNER_CODE placeholder and a known runner_kind (E16.15)."""
    report = ValidationReport()
    if not isinstance(value, dict):
        report.findings.append(ValidationFinding("error", "test_boilerplate must be an object"))
        return report
    body = value.get("body")
    if not isinstance(body, str) or "{{LEARNER_CODE}}" not in body:
        report.findings.append(
            ValidationFinding("error", "test_boilerplate.body must contain {{LEARNER_CODE}}")
        )
    kind = value.get("runnerKind") or value.get("runner_kind")
    if kind is not None and kind not in RUNNER_KINDS:
        report.findings.append(
            ValidationFinding(
                "error",
                f"unknown runner_kind `{kind}` (allowed: {', '.join(sorted(RUNNER_KINDS))})",
            )
        )
    stack = value.get("stack")
    if stack is not None and stack not in LESSON_STACKS:
        report.findings.append(ValidationFinding("error", f"unknown stack `{stack}` (allowed: {', '.join(sorted(LESSON_STACKS))})"))
    return report
