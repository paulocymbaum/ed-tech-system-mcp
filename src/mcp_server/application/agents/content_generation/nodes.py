"""LangGraph nodes for lesson → quiz + PBL content generation."""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from mcp_server.application.agents.content_generation.llm_output import (
    parse_structured_output,
    validation_error_messages,
)
from mcp_server.application.agents.content_generation.prompts import (
    lesson_system_prompt,
    lesson_user_prompt,
    pbl_system_prompt,
    pbl_user_prompt,
    quiz_system_prompt,
    quiz_user_prompt,
)
from mcp_server.application.agents.content_generation.state import ContentGenerationState
from mcp_server.application.llm import get_chat_model
from mcp_server.application.llm_model_name import resolve_invoked_model_name
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)
from mcp_server.application.workflow_llm_trace import record_llm_invocation
from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.harness_schemas import (
    HarnessLessonDraft,
    HarnessProjectDraft,
    HarnessQuizDraft,
)
from mcp_server.domain.llm_routing import LLMComplexity

_README_SECTION_RE = re.compile(r"^##\s+\S", re.MULTILINE)


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def max_validation_retries() -> int:
    """Maximum validation-driven retries before the graph gives up on an artifact."""
    return _workflow_runtime_config().validation_retries


def lesson_llm_complexity(state: ContentGenerationState) -> LLMComplexity:
    """README generation: MEDIUM on author pipeline (8b-class), HIGH for exploratory runs."""
    if state.get("fast_authoring"):
        return LLMComplexity.MEDIUM
    return LLMComplexity.HIGH


def quiz_pbl_llm_complexity(state: ContentGenerationState) -> LLMComplexity:
    """Quiz/project follow-ups: LOW on author pipeline, MEDIUM elsewhere."""
    if state.get("fast_authoring"):
        return LLMComplexity.LOW
    return LLMComplexity.MEDIUM


def _require_chat_model() -> BaseChatModel:
    model = get_chat_model()
    if model is None:
        raise ResourceNotFoundError("Chat model has not been initialized")
    return model


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


async def _invoke_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    model_type: type[LessonDraft]
    | type[QuizDraft]
    | type[PBLDraft]
    | type[HarnessLessonDraft]
    | type[HarnessQuizDraft]
    | type[HarnessProjectDraft],
    llm_complexity: LLMComplexity,
) -> tuple[
    LessonDraft
    | QuizDraft
    | PBLDraft
    | HarnessLessonDraft
    | HarnessQuizDraft
    | HarnessProjectDraft
    | None,
    list[str],
]:
    model = _require_chat_model()
    result = await model.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ],
        llm_complexity=int(llm_complexity),
    )
    raw_text = _message_content(result.content)
    record_llm_invocation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_output=raw_text,
        model_name=resolve_invoked_model_name(model),
        llm_complexity=int(llm_complexity),
    )
    try:
        parsed = parse_structured_output(raw_text, model_type)
    except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            return None, validation_error_messages(exc)
        return None, [str(exc)]
    return parsed, []


def _hit_value(hit: object, key: str) -> str | None:
    raw = getattr(hit, key, None)
    if raw is None and isinstance(hit, dict):
        raw = hit.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def graph_index_from_state(state: ContentGenerationState) -> str | None:
    """Prefer the selected graph hit's index over an LLM-invented value."""
    node_id = state.get("graph_node_id")
    node = node_id.strip() if isinstance(node_id, str) else ""
    for hit in state.get("graph_hits") or []:
        hit_id = _hit_value(hit, "node_id")
        if node and hit_id == node:
            return _hit_value(hit, "graph_index")
    for hit in state.get("graph_hits") or []:
        index = _hit_value(hit, "graph_index")
        if index:
            return index
    return None


def stamp_harness_lesson_identity(
    lesson: HarnessLessonDraft, state: ContentGenerationState
) -> HarnessLessonDraft:
    """Overwrite LLM graph ids with the values Teach already resolved."""
    node_id = state.get("graph_node_id")
    lesson_slug = state.get("lesson_slug")
    graph_index = graph_index_from_state(state) or lesson.meta.graph_index
    meta_update: dict[str, str] = {"graph_index": graph_index}
    if isinstance(node_id, str) and node_id.strip():
        meta_update["graph_node_id"] = node_id.strip()
    if isinstance(lesson_slug, str) and lesson_slug.strip():
        meta_update["id"] = lesson_slug.strip()
    return lesson.model_copy(update={"meta": lesson.meta.model_copy(update=meta_update)})


def stamp_harness_quiz_identity(
    quiz: HarnessQuizDraft, state: ContentGenerationState
) -> HarnessQuizDraft:
    """Align quiz lessonId / graphIndex with the lesson shell."""
    lesson_slug = state.get("lesson_slug")
    graph_index = graph_index_from_state(state)
    update: dict[str, str] = {}
    if isinstance(lesson_slug, str) and lesson_slug.strip():
        update["lesson_id"] = lesson_slug.strip()
    if graph_index:
        update["graph_index"] = graph_index
    if not update:
        return quiz
    return quiz.model_copy(update=update)


async def generate_lesson(state: ContentGenerationState) -> dict[str, object]:
    """Generate a structured lesson via Groq with router fallback."""
    graph_scoped = bool(state.get("graph_scoped"))
    model_type = HarnessLessonDraft if graph_scoped else LessonDraft
    lesson, errors = await _invoke_structured(
        system_prompt=lesson_system_prompt(graph_scoped=graph_scoped),
        user_prompt=lesson_user_prompt(
            topic=state["topic"],
            grade_level=state["grade_level"],
            validation_errors=state.get("lesson_validation_errors"),
            graph_scoped=graph_scoped,
            graph_hits=state.get("graph_hits"),
            graph_node_id=state.get("graph_node_id"),
            course_slug=state.get("course_slug"),
            lesson_slug=state.get("lesson_slug"),
        ),
        model_type=model_type,
        llm_complexity=lesson_llm_complexity(state),
    )
    if lesson is None:
        return {"lesson_validation_errors": errors}
    if graph_scoped and isinstance(lesson, HarnessLessonDraft):
        if not _README_SECTION_RE.search(lesson.readme_markdown):
            return {
                "lesson_validation_errors": [
                    "readme_markdown must include at least one ## section of teaching "
                    "content, not a quiz question list"
                ]
            }
        lesson = stamp_harness_lesson_identity(lesson, state)
    out: dict[str, object] = {"lesson": lesson, "lesson_validation_errors": []}
    if graph_scoped and isinstance(lesson, HarnessLessonDraft):
        out["harness_lesson"] = lesson
    return out


async def validate_lesson(state: ContentGenerationState) -> dict[str, object]:
    """Record a validation retry when lesson generation did not produce a valid artifact."""
    if state.get("lesson") is not None:
        return {}
    return {"lesson_retry_count": state.get("lesson_retry_count", 0) + 1}


async def generate_quiz(state: ContentGenerationState) -> dict[str, object]:
    """Generate a quiz from the validated lesson."""
    lesson = state.get("lesson")
    if lesson is None:
        return {"quiz_validation_errors": ["lesson is required before quiz generation"]}

    graph_scoped = bool(state.get("graph_scoped"))
    model_type = HarnessQuizDraft if graph_scoped else QuizDraft
    graph_index = None
    if isinstance(lesson, HarnessLessonDraft):
        graph_index = lesson.meta.graph_index

    quiz, errors = await _invoke_structured(
        system_prompt=quiz_system_prompt(graph_scoped=graph_scoped),
        user_prompt=quiz_user_prompt(
            topic=state["topic"],
            grade_level=state["grade_level"],
            lesson=lesson,
            validation_errors=state.get("quiz_validation_errors"),
            graph_scoped=graph_scoped,
            lesson_slug=state.get("lesson_slug"),
            graph_index=graph_index,
        ),
        model_type=model_type,
        llm_complexity=quiz_pbl_llm_complexity(state),
    )
    if quiz is None:
        return {"quiz_validation_errors": errors}
    if graph_scoped and isinstance(quiz, HarnessQuizDraft):
        quiz = stamp_harness_quiz_identity(quiz, state)
    out: dict[str, object] = {"quiz": quiz, "quiz_validation_errors": []}
    if graph_scoped and isinstance(quiz, HarnessQuizDraft):
        out["harness_quiz"] = quiz
    return out


async def validate_quiz(state: ContentGenerationState) -> dict[str, object]:
    """Record a validation retry when quiz generation did not produce a valid artifact."""
    if state.get("quiz") is not None:
        return {}
    return {"quiz_retry_count": state.get("quiz_retry_count", 0) + 1}


async def generate_pbl(state: ContentGenerationState) -> dict[str, object]:
    """Generate a PBL project from the validated lesson."""
    lesson = state.get("lesson")
    if lesson is None:
        return {"pbl_validation_errors": ["lesson is required before PBL generation"]}

    graph_scoped = bool(state.get("graph_scoped"))
    model_type = HarnessProjectDraft if graph_scoped else PBLDraft
    graph_index = None
    if isinstance(lesson, HarnessLessonDraft):
        graph_index = lesson.meta.graph_index

    pbl, errors = await _invoke_structured(
        system_prompt=pbl_system_prompt(graph_scoped=graph_scoped),
        user_prompt=pbl_user_prompt(
            topic=state["topic"],
            grade_level=state["grade_level"],
            lesson=lesson,
            validation_errors=state.get("pbl_validation_errors"),
            graph_scoped=graph_scoped,
            lesson_slug=state.get("lesson_slug"),
            graph_index=graph_index,
        ),
        model_type=model_type,
        llm_complexity=quiz_pbl_llm_complexity(state),
    )
    if pbl is None:
        return {"pbl_validation_errors": errors}
    out: dict[str, object] = {"pbl": pbl, "pbl_validation_errors": []}
    if graph_scoped and isinstance(pbl, HarnessProjectDraft):
        out["harness_project"] = pbl
    return out


async def validate_pbl(state: ContentGenerationState) -> dict[str, object]:
    """Record a validation retry when PBL generation did not produce a valid artifact."""
    if state.get("pbl") is not None:
        return {}
    return {"pbl_retry_count": state.get("pbl_retry_count", 0) + 1}


async def merge_results(state: ContentGenerationState) -> dict[str, object]:
    """Terminal node that marks the workflow complete for UI inspection."""
    return {"generation_complete": True}
