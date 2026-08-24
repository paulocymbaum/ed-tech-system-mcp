"""Prompt templates for structured content generation."""

from __future__ import annotations

import json

from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft
from mcp_server.domain.harness_schemas import (
    HarnessLessonDraft,
    HarnessProjectDraft,
    HarnessQuizDraft,
)
from mcp_server.domain.input_safety import wrap_user_content_for_prompt


def _graph_context_lines(
    *,
    graph_hits: list[object] | None,
    graph_node_id: str | None,
    course_slug: str | None,
    lesson_slug: str | None,
) -> list[str]:
    lines: list[str] = []
    if course_slug:
        lines.append(f"Target course slug: {course_slug}")
    if lesson_slug:
        lines.append(f"Target lesson slug: {lesson_slug}")
    if graph_node_id:
        lines.append(f"Graph node id (must use in meta.graphNodeId): {graph_node_id}")
    if graph_hits:
        lines.append("Curriculum graph grounding (search_graph_nodes):")
        for hit in graph_hits[:5]:
            label = getattr(hit, "label", None) or (
                hit.get("label") if isinstance(hit, dict) else ""
            )
            idx = getattr(hit, "graph_index", None) or (
                hit.get("graph_index") if isinstance(hit, dict) else None
            )
            node = getattr(hit, "node_id", None) or (
                hit.get("node_id") if isinstance(hit, dict) else None
            )
            if label:
                lines.append(f"- {label} (graph_index={idx}, node_id={node})")
    return lines


def lesson_system_prompt(*, graph_scoped: bool = False) -> str:
    schema = HarnessLessonDraft if graph_scoped else LessonDraft
    return (
        "You are an expert curriculum designer. Respond with a single JSON object only, "
        "no markdown fences or commentary. Match this schema:\n"
        f"{json.dumps(schema.model_json_schema(), indent=2)}"
    )


def lesson_user_prompt(
    *,
    topic: str,
    grade_level: str,
    validation_errors: list[str] | None,
    graph_scoped: bool = False,
    graph_hits: list[object] | None = None,
    graph_node_id: str | None = None,
    course_slug: str | None = None,
    lesson_slug: str | None = None,
) -> str:
    topic_block = wrap_user_content_for_prompt(topic, label="topic")
    grade_block = wrap_user_content_for_prompt(grade_level, label="grade_level")
    lines = [
        "Create a lesson using the topic and grade level provided below.",
        topic_block,
        grade_block,
    ]
    lines.extend(
        _graph_context_lines(
            graph_hits=graph_hits,
            graph_node_id=graph_node_id,
            course_slug=course_slug,
            lesson_slug=lesson_slug,
        )
    )
    if graph_scoped:
        lines.append(
            "Produce readme_markdown (Markdown with # title and ## sections) and meta "
            "with graphIndex, graphNodeId, id, and title aligned to the graph node."
        )
    else:
        lines.append(
            "Include clear objectives, at least two sections with substantive content, "
            "and a summary."
        )
    lines.append(
        "Do not include a 'Prove what you learned' section, assessment call-to-action buttons, "
        "or links/buttons to quizzes or projects in the readme_markdown. The LMS renders the "
        "lesson's quiz and project actions separately in the UI, so including them would "
        "duplicate controls."
    )
    if validation_errors:
        lines.append("Fix these validation errors from your previous attempt:")
        lines.extend(f"- {error}" for error in validation_errors)
    return "\n".join(lines)


def quiz_system_prompt(*, graph_scoped: bool = False) -> str:
    schema = HarnessQuizDraft if graph_scoped else QuizDraft
    return (
        "You are an assessment designer. Respond with a single JSON object only, "
        "no markdown fences or commentary. Match this schema:\n"
        f"{json.dumps(schema.model_json_schema(), indent=2)}"
    )


def quiz_user_prompt(
    *,
    topic: str,
    grade_level: str,
    lesson: LessonDraft | HarnessLessonDraft,
    validation_errors: list[str] | None,
    graph_scoped: bool = False,
    lesson_slug: str | None = None,
    graph_index: str | None = None,
) -> str:
    if isinstance(lesson, HarnessLessonDraft):
        lesson_title = lesson.meta.title
        objectives = lesson.meta.lesson_dependencies
    else:
        lesson_title = lesson.title
        objectives = lesson.objectives
    lines = [
        "Create a quiz using the topic and grade level provided below.",
        wrap_user_content_for_prompt(topic, label="topic"),
        wrap_user_content_for_prompt(grade_level, label="grade_level"),
        f"Base the quiz on this lesson title: {lesson_title}",
    ]
    if graph_scoped:
        lines.append(
            "Each question MUST have exactly four options with slug ids a, b, c, and d "
            "(one object per letter, all four required). "
            "correctOptionId MUST be exactly one option.id — never the option text, "
            "never an index, never a UUID. Include a short explanation per question."
        )
        if lesson_slug:
            lines.append(f"Set lessonId to: {lesson_slug}")
        if graph_index:
            lines.append(f"Set graphIndex to: {graph_index}")
    else:
        lines.append("Objectives:")
        lines.extend(f"- {objective}" for objective in objectives)
        lines.append("Include at least three multiple-choice questions with explanations.")
        lines.append(
            "Each question needs exactly four unique options (ids a, b, c, d) "
            "and correctOptionId equal to one of those ids."
        )
    if validation_errors:
        lines.append("Fix these validation errors from your previous attempt:")
        lines.extend(f"- {error}" for error in validation_errors)
    return "\n".join(lines)


def pbl_system_prompt(*, graph_scoped: bool = False) -> str:
    schema = HarnessProjectDraft if graph_scoped else PBLDraft
    return (
        "You are a PBL curriculum designer. Respond with a single JSON object only, "
        "no markdown fences or commentary. Match this schema:\n"
        f"{json.dumps(schema.model_json_schema(), indent=2)}"
    )


def pbl_user_prompt(
    *,
    topic: str,
    grade_level: str,
    lesson: LessonDraft | HarnessLessonDraft,
    validation_errors: list[str] | None,
    graph_scoped: bool = False,
    lesson_slug: str | None = None,
    graph_index: str | None = None,
) -> str:
    if isinstance(lesson, HarnessLessonDraft):
        lesson_title = lesson.meta.title
        summary = lesson.readme_markdown[:400]
    else:
        lesson_title = lesson.title
        summary = lesson.summary
    lines = [
        "Design a problem-based learning project using the topic and grade level below.",
        wrap_user_content_for_prompt(topic, label="topic"),
        wrap_user_content_for_prompt(grade_level, label="grade_level"),
        f"Anchor the project in this lesson: {lesson_title}",
        "Lesson summary:",
        summary,
    ]
    if graph_scoped:
        lines.append(
            "Include readme_markdown with required PBL sections, starter/index.js, "
            "starter/tests.json cases, and files[] + test_cases[] for backend upsert. "
            "Every test_cases entry needs id, stdin, and expectedStdout."
        )
        if lesson_slug and graph_index:
            lines.append(
                f"Use slug like 001-{topic[:20].lower().replace(' ', '-')}, "
                f"root_path lessons/{lesson_slug}/projects/001-<slug>/, graph_index {graph_index}."
            )
    else:
        lines.append(
            "Include a driving question, realistic scenario, objectives, and deliverables."
        )
    if validation_errors:
        lines.append("Fix these validation errors from your previous attempt:")
        lines.extend(f"- {error}" for error in validation_errors)
    return "\n".join(lines)
