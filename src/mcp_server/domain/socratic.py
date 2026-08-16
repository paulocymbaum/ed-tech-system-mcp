"""Socratic tutor domain (E8) — policies and I/O schemas. Never grades."""

from __future__ import annotations

import re
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

SUPPORTED_LOCALES = ("en", "pt", "es", "zh")
LocaleCode = Literal["en", "pt", "es", "zh"]

MAX_REPLY_LINES = 12
HINT_LEVELS = (1, 2, 3, 4, 5)

BANNED_GRADE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bscore\s*[:=]?\s*\d{1,3}\b", re.I),
    re.compile(r"\b(grade|grading|mark(ed|ing)?)\b.*\b(done|pass|fail)\b", re.I),
    re.compile(r"\b(out of|/)\s*100\b", re.I),
    re.compile(r"\breview[- ]course[- ]project\b", re.I),
    re.compile(r"\bproject[- ]delivery\.json\b", re.I),
)


class SocraticMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class SocraticGraphHit(BaseModel):
    label: str
    path: str | None = None
    score: float | None = None


class SocraticDocHit(BaseModel):
    title: str
    snippet: str


class SocraticGrounding(BaseModel):
    lesson_markdown: str = ""
    project_readme: str = ""
    graph_hits: list[SocraticGraphHit] = Field(default_factory=list)
    documents: list[SocraticDocHit] = Field(default_factory=list)

    @field_validator("lesson_markdown", "project_readme", mode="before")
    @classmethod
    def _coerce_optional_str(cls, value: object) -> str:
        return "" if value is None else str(value)


class SocraticReply(BaseModel):
    reply: str
    hint_level: int = Field(ge=1, le=5)
    locale: LocaleCode = "en"
    asked_full_solution: bool = False
    grounding_used: bool = False


class SocraticCatalogPort(Protocol):
    """Port for course catalog + graph topic grounding."""

    def load_grounding(
        self,
        *,
        tenant_id: str,
        course_slug: str,
        module_slug: str | None,
        lesson_slug: str | None,
        project_slug: str | None,
        query: str,
    ) -> SocraticGrounding: ...


def normalize_locale(value: str | None) -> LocaleCode:
    raw = (value or "en").strip().lower()[:2]
    if raw in SUPPORTED_LOCALES:
        return raw  # type: ignore[return-value]
    return "en"


def tutor_turn_index(history: list[SocraticMessage] | None) -> int:
    """1-based assistant turn about to be produced (empty history → turn 1)."""
    if not history:
        return 1
    prior = 0
    for message in history:
        role = getattr(message, "role", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
        if role == "assistant":
            prior += 1
    return prior + 1


_FENCE_BLOCK = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n([\s\S]*?)```")
_COMPLETE_FN = re.compile(
    r"\b(function|def|class|const\s+\w+\s*=\s*\()",
    re.I,
)


def _looks_complete_solution(body: str) -> bool:
    lines = [line for line in body.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    return bool(_COMPLETE_FN.search(body)) and bool(re.search(r"\breturn\b", body, re.I))


def validate_socratic_reply(
    reply: str,
    *,
    asked_full_solution: bool = False,
    turn_index: int = 1,
) -> dict[str, Any]:
    """Enforce tutor policies: no grading, short turns, questions-first bias."""
    errors: list[str] = []
    warnings: list[str] = []
    text = reply.strip()
    if not text:
        return {"ok": False, "errors": ["Reply is empty."], "warnings": warnings}

    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) > MAX_REPLY_LINES:
        errors.append(f"Reply has {len(lines)} lines; max {MAX_REPLY_LINES}.")

    for pattern in BANNED_GRADE_PATTERNS:
        if pattern.search(text):
            errors.append("Tutor must not grade or assign scores.")
            break

    if not asked_full_solution:
        for fence in _FENCE_BLOCK.finditer(text):
            body = fence.group(1)
            if len(body) >= 400:
                errors.append("Full solution code dump blocked unless user asked.")
                break
            if turn_index <= 1 and _looks_complete_solution(body):
                errors.append("Full solution code dump blocked unless user asked.")
                break

        question_marks = text.count("?")
        if question_marks < 1:
            warnings.append("Prefer ending with at least one Socratic question.")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}
