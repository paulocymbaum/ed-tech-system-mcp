"""Prompts for Socratic tutor (E8)."""

from __future__ import annotations

from mcp_server.domain.socratic import SocraticGrounding, SocraticMessage

_LOCALE_NAMES = {
    "en": "English",
    "pt": "Portuguese",
    "es": "Spanish",
    "zh": "Chinese",
}


def socratic_system_prompt(*, locale: str, hint_level: int, want_full_solution: bool) -> str:
    lang = _LOCALE_NAMES.get(locale, "English")
    ladder = {
        1: "Clarify the goal and constraints with questions only.",
        2: "Ask for the learner's current approach / reasoning.",
        3: "Offer one small hint (one missing concept) plus a question.",
        4: "Offer a stronger outline hint; still no full solution.",
        5: "Provide a minimal full solution only if requested, then check understanding.",
    }[max(1, min(5, hint_level))]

    solution_rule = (
        "User asked for a full solution — give the minimal answer, then 1–2 understanding checks."
        if want_full_solution or hint_level >= 5
        else "Do NOT dump a full solution. Prefer questions before answers."
    )

    return f"""You are a Socratic tutor for an LMS (persona: warm, concise, Deep Thought–curious).
Respond in {lang}. Keep code identifiers/paths unchanged.
Never assign grades, scores, or mark projects done.
Hint ladder step {hint_level}/5: {ladder}
{solution_rule}
Rules:
- Reflect first (1 short sentence).
- Most replies: 3–8 lines; max ~12 lines.
- 1–2 Socratic questions max (3 only if yes/no).
- Include one small visual when helpful (Mermaid or tiny ASCII), not huge dumps.
- One next action only.
- Never mention delivery tabs, score.json, or Cursor skills.
Return plain markdown text only (no JSON wrapper)."""


def socratic_user_prompt(
    *,
    message: str,
    history: list[SocraticMessage],
    grounding: SocraticGrounding | None,
    course_slug: str,
    module_slug: str | None,
    lesson_slug: str | None,
    project_slug: str | None,
) -> str:
    parts: list[str] = [
        f"Course: {course_slug}",
    ]
    if module_slug:
        parts.append(f"Module: {module_slug}")
    if lesson_slug:
        parts.append(f"Lesson: {lesson_slug}")
    if project_slug:
        parts.append(f"Project: {project_slug}")

    if grounding:
        if grounding.lesson_markdown:
            parts.append("Lesson excerpt:\n" + grounding.lesson_markdown[:2500])
        if grounding.project_readme:
            parts.append("Project README excerpt:\n" + grounding.project_readme[:2000])
        if grounding.graph_hits:
            hits = "; ".join(
                f"{h.label}" + (f" ({h.path})" if h.path else "")
                for h in grounding.graph_hits[:5]
            )
            parts.append(f"Graph topics: {hits}")
        if grounding.documents:
            docs = "\n".join(
                f"- {d.title}: {d.snippet[:240]}" for d in grounding.documents[:3]
            )
            parts.append(f"Related documents:\n{docs}")

    if history:
        hist = "\n".join(f"{m.role}: {m.content[:500]}" for m in history[-6:])
        parts.append(f"Recent chat:\n{hist}")

    parts.append(f"Learner message:\n{message}")
    return "\n\n".join(parts)
