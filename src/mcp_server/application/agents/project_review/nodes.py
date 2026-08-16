"""LangGraph nodes for project review."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from mcp_server.application.agents.project_review.prompts import (
    grade_system_prompt,
    grade_user_prompt,
)
from mcp_server.application.agents.project_review.state import ProjectReviewState
from mcp_server.application.llm import get_chat_model
from mcp_server.application.llm_model_name import resolve_invoked_model_name
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.llm_routing import LLMComplexity
from mcp_server.domain.project_review import (
    GroqModelErrorReporterPort,
    ProjectReviewGrade,
    ProjectReviewResult,
    ProjectReviewStore,
    validate_review_comment,
)

_repo: ProjectReviewStore | None = None
_error_reporter: GroqModelErrorReporterPort | None = None


def register_project_review_repository(repo: ProjectReviewStore) -> None:
    global _repo
    _repo = repo


def register_project_review_error_reporter(
    reporter: GroqModelErrorReporterPort,
) -> None:
    global _error_reporter
    _error_reporter = reporter


def _require_repo() -> ProjectReviewStore:
    if _repo is None:
        raise ResourceNotFoundError("Project review repository not initialized")
    return _repo


def _report_groq_model_error(*, model: str, error_type: str = "completion_error") -> None:
    if _error_reporter is None:
        return
    _error_reporter.report(model=model, error_type=error_type)


def _message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def _parse_grade_json(text: str) -> ProjectReviewGrade:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Grade payload must be a JSON object")
    return ProjectReviewGrade(score=int(data["score"]), comment=str(data["comment"]))


async def collect_context(state: ProjectReviewState) -> dict[str, Any]:
    repo = _require_repo()
    context = await asyncio.to_thread(
        repo.collect_context,
        tenant_id=state["tenant_id"],
        course_slug=state["course_slug"],
        module_slug=state["module_slug"],
        lesson_slug=state["lesson_slug"],
        project_slug=state["project_slug"],
        user_id=state["user_id"],
        delivery_limit=int(state.get("delivery_limit") or 3),
    )
    return {"context": context, "error": None}


async def grade_delivery(state: ProjectReviewState) -> dict[str, Any]:
    context = state.get("context")
    if context is None:
        return {"error": "missing_context"}
    if not context.deliveries:
        return {
            "score": 0,
            "comment": (
                "No solution code in the latest delivery to evaluate. "
                "Next: submit your working solution against the README acceptance criteria."
            ),
            "model_id": None,
        }

    model = get_chat_model()
    if model is None:
        raise ResourceNotFoundError("Chat model has not been initialized")

    messages = [
        SystemMessage(content=grade_system_prompt()),
        HumanMessage(content=grade_user_prompt(context)),
    ]
    try:
        response = await model.ainvoke(
            messages,
            llm_complexity=int(LLMComplexity.MEDIUM),
        )
    except Exception as exc:  # noqa: BLE001 — report + surface as state error
        model_id = resolve_invoked_model_name(model)
        _report_groq_model_error(model=model_id or "unknown", error_type="completion_error")
        return {"error": f"llm_failed:{exc}", "model_id": model_id}

    text = _message_content(response.content)
    model_id = resolve_invoked_model_name(model)
    try:
        grade = _parse_grade_json(text)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"parse_failed:{exc}", "model_id": model_id}

    return {
        "score": grade.score,
        "comment": grade.comment,
        "model_id": model_id,
        "validation_errors": [],
        "error": None,
    }


async def validate_grade(state: ProjectReviewState) -> dict[str, Any]:
    score = state.get("score")
    comment = state.get("comment")
    retries = int(state.get("grade_retry_count") or 0)
    if score is None or not comment:
        return {"validation_errors": ["missing_score_or_comment"], "grade_retry_count": retries}
    check = validate_review_comment(comment)
    if not check["ok"]:
        return {
            "validation_errors": list(check["errors"]),
            "grade_retry_count": retries + 1,
        }
    if not (0 <= int(score) <= 100):
        return {"validation_errors": ["score_out_of_range"], "grade_retry_count": retries + 1}
    return {"validation_errors": [], "grade_retry_count": retries}


async def persist_grade(state: ProjectReviewState) -> dict[str, Any]:
    context = state.get("context")
    score = state.get("score")
    comment = state.get("comment")
    if context is None or score is None or not comment:
        return {"error": "missing_grade"}
    delivery_id = context.latest_delivery_id
    if not delivery_id:
        return {"error": "missing_delivery"}

    if not state.get("persist", True):
        return {
            "result": ProjectReviewResult(
                score=int(score),
                comment=comment,
                passed=int(score) > 80,
                delivery_id=delivery_id,
                persisted=False,
                model_id=state.get("model_id"),
            )
        }

    repo = _require_repo()
    grade = ProjectReviewGrade(score=int(score), comment=comment)
    result = repo.persist_grade(delivery_id=delivery_id, grade=grade)
    result.model_id = state.get("model_id")
    return {"result": result, "error": None}
