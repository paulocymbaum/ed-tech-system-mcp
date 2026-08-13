"""Prompts for AI project delivery grading."""

from __future__ import annotations

from mcp_server.domain.project_review import ProjectReviewContext


def grade_system_prompt() -> str:
    return (
        "You are a strict but fair coding project grader for a PBL exercise.\n"
        "Score integer 0-100 against the project README acceptance criteria only.\n"
        "Pass threshold is score > 80.\n"
        "The latest delivery content IS the submission (usually includes solution code).\n"
        "Starter template TODO stubs must NOT lower the score.\n"
        "Do not require matching any reference solution.\n"
        "Out of scope: study app UI, delivery workflow, tooling, repo architecture.\n"
        "Comment: 2-4 plain sentences, max 480 characters, max 5 lines. "
        "No markdown headers or bold labels. End with 'Next: <one fix>' when score <= 80.\n"
        "Respond with JSON only: {\"score\": <int>, \"comment\": \"<text>\"}."
    )


def grade_user_prompt(context: ProjectReviewContext) -> str:
    starter = "\n\n".join(
        f"### {f.path}\n```\n{f.content[:8000]}\n```" for f in context.starter_files
    ) or "(no starter files)"
    deliveries = []
    for index, delivery in enumerate(context.deliveries, start=1):
        deliveries.append(
            f"### Delivery {index} id={delivery.id} at={delivery.submitted_at}\n"
            f"{delivery.content[:12000]}"
        )
    delivery_block = "\n\n".join(deliveries) or "(no deliveries)"
    latest = context.deliveries[-1].content[:16000] if context.deliveries else "(none)"
    return (
        f"## Lesson context\n{context.lesson_markdown[:6000] or '(none)'}\n\n"
        f"## Project README\n{context.readme_markdown[:12000] or '(none)'}\n\n"
        f"## Starter template\n{starter}\n\n"
        f"## Last deliveries (oldest → newest)\n{delivery_block}\n\n"
        f"## Latest delivery (grade this)\n{latest}\n"
    )
