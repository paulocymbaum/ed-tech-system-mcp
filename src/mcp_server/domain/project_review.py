"""Project delivery review domain (E7) — comment rules and result schemas."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

MAX_REVIEW_COMMENT_LENGTH = 480
MAX_REVIEW_COMMENT_LINES = 5

BANNED_COMMENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bdelivery tab\b", re.I),
    re.compile(r"\bproject-delivery\.json\b", re.I),
    re.compile(r"\bscore\.json\b", re.I),
    re.compile(r"\bstudy app\b", re.I),
    re.compile(r"\breview-course-project\b", re.I),
    re.compile(r"\bteacher-socratic\b", re.I),
    re.compile(r"\bcursor skill\b", re.I),
    re.compile(r"\bcatalog\.json\b", re.I),
    re.compile(r"\brepo architecture\b", re.I),
    re.compile(r"\bsubmit(ted|ting)? deliveries?\b", re.I),
    re.compile(r"\bdelivery workflow\b", re.I),
    re.compile(r"\b(copy|sync|move).*(into|to) starter\b", re.I),
    re.compile(r"\bstarter/.*\b(still|not updated|todo|stub|not implemented)\b", re.I),
)


class ProjectReviewDelivery(BaseModel):
    id: str
    content: str
    submitted_at: str
    review: dict[str, Any] | None = None


class ProjectReviewFile(BaseModel):
    path: str
    content: str


class ProjectReviewContext(BaseModel):
    tenant_id: str
    course_slug: str
    module_slug: str
    lesson_slug: str
    project_slug: str
    project_id: str
    user_id: str
    readme_markdown: str = ""
    lesson_markdown: str = ""
    starter_files: list[ProjectReviewFile] = Field(default_factory=list)
    deliveries: list[ProjectReviewDelivery] = Field(default_factory=list)
    latest_delivery_id: str | None = None


class ProjectReviewGrade(BaseModel):
    score: int = Field(ge=0, le=100)
    comment: str = Field(min_length=1, max_length=MAX_REVIEW_COMMENT_LENGTH)

    @field_validator("comment")
    @classmethod
    def _validate_comment(cls, value: str) -> str:
        result = validate_review_comment(value)
        if not result["ok"]:
            raise ValueError("; ".join(result["errors"]))
        return value.strip()


class ProjectReviewResult(BaseModel):
    score: int
    comment: str
    passed: bool
    delivery_id: str
    persisted: bool = False
    progress_updated: bool = False
    review_id: str | None = None
    model_id: str | None = None


def validate_review_comment(comment: str) -> dict[str, Any]:
    """Port of PraxisWeb review-comment.mjs rules."""
    errors: list[str] = []
    warnings: list[str] = []
    text = comment.strip()
    if not text:
        return {"ok": False, "errors": ["Comment is empty."], "warnings": warnings}
    if len(text) > MAX_REVIEW_COMMENT_LENGTH:
        errors.append(
            f"Comment is {len(text)} chars; max {MAX_REVIEW_COMMENT_LENGTH}."
        )
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) > MAX_REVIEW_COMMENT_LINES:
        errors.append(
            f"Comment has {len(lines)} non-empty lines; max {MAX_REVIEW_COMMENT_LINES}."
        )
    if re.search(r"^#{1,6}\s", text, re.M) or re.search(r"\*\*[^*]+\*\*", text):
        warnings.append("Prefer plain sentences over markdown headings or bold labels.")
    for pattern in BANNED_COMMENT_PATTERNS:
        if pattern.search(text):
            errors.append(f"Comment mentions out-of-scope topic (matched: {pattern.pattern}).")
            break
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}
