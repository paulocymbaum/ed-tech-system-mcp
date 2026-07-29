"""LangGraph nodes for lesson → quiz + PBL content generation."""

from __future__ import annotations

import json
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
from mcp_server.domain.llm_routing import LLMComplexity


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def max_validation_retries() -> int:
    """Maximum validation-driven retries before the graph gives up on an artifact."""
    return _workflow_runtime_config().node_retries


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
    model_type: type[LessonDraft] | type[QuizDraft] | type[PBLDraft],
    llm_complexity: LLMComplexity,
) -> tuple[LessonDraft | QuizDraft | PBLDraft | None, list[str]]:
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


async def generate_lesson(state: ContentGenerationState) -> dict[str, object]:
    """Generate a structured lesson via Groq with router fallback."""
    lesson, errors = await _invoke_structured(
        system_prompt=lesson_system_prompt(),
        user_prompt=lesson_user_prompt(
            topic=state["topic"],
            grade_level=state["grade_level"],
            validation_errors=state.get("lesson_validation_errors"),
        ),
        model_type=LessonDraft,
        llm_complexity=LLMComplexity.HIGH,
    )
    if lesson is None:
        return {"lesson_validation_errors": errors}
    return {
        "lesson": lesson,
        "lesson_validation_errors": [],
    }


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

    quiz, errors = await _invoke_structured(
        system_prompt=quiz_system_prompt(),
        user_prompt=quiz_user_prompt(
            topic=state["topic"],
            grade_level=state["grade_level"],
            lesson=lesson,
            validation_errors=state.get("quiz_validation_errors"),
        ),
        model_type=QuizDraft,
        llm_complexity=LLMComplexity.MEDIUM,
    )
    if quiz is None:
        return {"quiz_validation_errors": errors}
    return {
        "quiz": quiz,
        "quiz_validation_errors": [],
    }


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

    pbl, errors = await _invoke_structured(
        system_prompt=pbl_system_prompt(),
        user_prompt=pbl_user_prompt(
            topic=state["topic"],
            grade_level=state["grade_level"],
            lesson=lesson,
            validation_errors=state.get("pbl_validation_errors"),
        ),
        model_type=PBLDraft,
        llm_complexity=LLMComplexity.MEDIUM,
    )
    if pbl is None:
        return {"pbl_validation_errors": errors}
    return {
        "pbl": pbl,
        "pbl_validation_errors": [],
    }


async def validate_pbl(state: ContentGenerationState) -> dict[str, object]:
    """Record a validation retry when PBL generation did not produce a valid artifact."""
    if state.get("pbl") is not None:
        return {}
    return {"pbl_retry_count": state.get("pbl_retry_count", 0) + 1}


async def merge_results(state: ContentGenerationState) -> dict[str, object]:
    """Terminal node that marks the workflow complete for UI inspection."""
    return {"generation_complete": True}
