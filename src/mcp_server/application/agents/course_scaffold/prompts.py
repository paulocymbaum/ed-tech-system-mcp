"""Prompts for structure-only course scaffold generation."""

from __future__ import annotations


def scaffold_system_prompt() -> str:
    return (
        "You design course topic graphs for an LMS. Return JSON only with keys "
        "`nodes` and `edges`. Each node must have legacy_node_id, label, kind, "
        "and graph_index. kind is one of: root, module, lesson, section. "
        "Exactly one root. graph_index values must be unique hierarchical strings "
        "(example: 00, 01, 01.1). Edges use parent_legacy_id and child_legacy_id "
        "and must form a connected tree from the root. "
        "Do not include README, markdown, quiz, project, questions, tests, body, "
        "or other lesson content fields."
    )


def scaffold_user_prompt(
    *,
    prompt: str,
    title: str | None,
    locale: str | None,
    slug: str | None,
    course_slug: str | None,
    validation_errors: list[str] | None = None,
) -> str:
    lines = [
        "Create a structure-only course outline.",
        f"Teacher prompt: {prompt.strip()}",
    ]
    if title:
        lines.append(f"Course title: {title.strip()}")
    if locale:
        lines.append(f"Locale: {locale.strip()}")
    identity = course_slug or slug
    if identity:
        lines.append(f"Course slug: {identity.strip()}")
    lines.append(
        "Include a root node for the course, at least two modules, and at least "
        "one lesson under each module."
    )
    if validation_errors:
        lines.append("Fix these validation errors:")
        lines.extend(f"- {error}" for error in validation_errors)
    return "\n".join(lines)
