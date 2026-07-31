"""Prompt templates for structured content generation."""

from __future__ import annotations

import json

from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft
from mcp_server.domain.input_safety import wrap_user_content_for_prompt


def lesson_system_prompt() -> str:
    return (
        "You are an expert curriculum designer. Respond with a single JSON object only, "
        "no markdown fences or commentary. Match this schema:\n"
        f"{json.dumps(LessonDraft.model_json_schema(), indent=2)}"
    )


def lesson_user_prompt(*, topic: str, grade_level: str, validation_errors: list[str] | None) -> str:
    topic_block = wrap_user_content_for_prompt(topic, label="topic")
    grade_block = wrap_user_content_for_prompt(grade_level, label="grade_level")
    lines = [
        "Create a lesson using the topic and grade level provided below.",
        topic_block,
        grade_block,
        "Include clear objectives, at least two sections with substantive content, and a summary.",
    ]
    if validation_errors:
        lines.append("Fix these validation errors from your previous attempt:")
        lines.extend(f"- {error}" for error in validation_errors)
    return "\n".join(lines)


def quiz_system_prompt() -> str:
    return (
        "You are an assessment designer. Respond with a single JSON object only, "
        "no markdown fences or commentary. Match this schema:\n"
        f"{json.dumps(QuizDraft.model_json_schema(), indent=2)}"
    )


def quiz_user_prompt(
    *,
    topic: str,
    grade_level: str,
    lesson: LessonDraft,
    validation_errors: list[str] | None,
) -> str:
    lines = [
        "Create a quiz using the topic and grade level provided below.",
        wrap_user_content_for_prompt(topic, label="topic"),
        wrap_user_content_for_prompt(grade_level, label="grade_level"),
        f"Base the quiz on this lesson title: {lesson.title}",
        "Objectives:",
        *[f"- {objective}" for objective in lesson.objectives],
        "Include at least three multiple-choice questions with explanations.",
    ]
    if validation_errors:
        lines.append("Fix these validation errors from your previous attempt:")
        lines.extend(f"- {error}" for error in validation_errors)
    return "\n".join(lines)


def pbl_system_prompt() -> str:
    return (
        "You are a PBL curriculum designer. Respond with a single JSON object only, "
        "no markdown fences or commentary. Match this schema:\n"
        f"{json.dumps(PBLDraft.model_json_schema(), indent=2)}"
    )


def pbl_user_prompt(
    *,
    topic: str,
    grade_level: str,
    lesson: LessonDraft,
    validation_errors: list[str] | None,
) -> str:
    lines = [
        "Design a problem-based learning project using the topic and grade level below.",
        wrap_user_content_for_prompt(topic, label="topic"),
        wrap_user_content_for_prompt(grade_level, label="grade_level"),
        f"Anchor the project in this lesson: {lesson.title}",
        "Lesson summary:",
        lesson.summary,
        "Include a driving question, realistic scenario, objectives, and deliverables.",
    ]
    if validation_errors:
        lines.append("Fix these validation errors from your previous attempt:")
        lines.extend(f"- {error}" for error in validation_errors)
    return "\n".join(lines)
