"""LangGraph nodes for structure-only course scaffold generation."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from mcp_server.application.agents.content_generation.llm_output import (
    extract_json_object,
    parse_structured_output,
    validation_error_messages,
)
from mcp_server.application.agents.course_scaffold.prompts import (
    scaffold_system_prompt,
    scaffold_user_prompt,
)
from mcp_server.application.agents.course_scaffold.state import CourseScaffoldState
from mcp_server.application.llm import get_chat_model
from mcp_server.application.llm_model_name import resolve_invoked_model_name
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)
from mcp_server.application.workflow_llm_trace import record_llm_invocation
from mcp_server.domain.course_scaffold import (
    ScaffoldProposal,
    raw_forbidden_body_keys,
    validate_scaffold_proposal,
)
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.llm_routing import LLMComplexity


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def max_validation_retries() -> int:
    """Maximum validation-driven retries before the graph gives up."""
    return _workflow_runtime_config().validation_retries


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


async def generate(state: CourseScaffoldState) -> dict[str, object]:
    """Generate a structure-only proposal via Groq."""
    model = _require_chat_model()
    system_prompt = scaffold_system_prompt()
    user_prompt = scaffold_user_prompt(
        prompt=state["prompt"],
        title=state.get("title"),
        locale=state.get("locale"),
        slug=state.get("slug"),
        course_slug=state.get("course_slug"),
        validation_errors=state.get("validation_errors"),
    )
    result = await model.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)],
        llm_complexity=int(LLMComplexity.MEDIUM),
    )
    raw_text = _message_content(result.content)
    record_llm_invocation(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        raw_output=raw_text,
        model_name=resolve_invoked_model_name(model),
        llm_complexity=int(LLMComplexity.MEDIUM),
    )
    try:
        payload = extract_json_object(raw_text)
        forbidden = raw_forbidden_body_keys(payload)
        if forbidden:
            return {
                "proposal": None,
                "validation_errors": [
                    f"forbidden lesson body keys: {', '.join(sorted(set(forbidden)))}"
                ],
            }
        parsed = parse_structured_output(raw_text, ScaffoldProposal)
    except (ValidationError, json.JSONDecodeError, TypeError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            return {"proposal": None, "validation_errors": validation_error_messages(exc)}
        return {"proposal": None, "validation_errors": [str(exc)]}
    findings = validate_scaffold_proposal(parsed)
    if findings:
        return {"proposal": None, "validation_errors": findings}
    return {"proposal": parsed, "validation_errors": []}


async def validate(state: CourseScaffoldState) -> dict[str, object]:
    """Record a validation retry when generation did not produce a valid graph."""
    if state.get("proposal") is not None:
        return {"generation_complete": True}
    return {"generate_retry_count": state.get("generate_retry_count", 0) + 1}
