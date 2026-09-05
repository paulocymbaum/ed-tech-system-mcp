"""LangGraph nodes for socratic tutor."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from mcp_server.application.agents.socratic.prompts import (
    socratic_system_prompt,
    socratic_user_prompt,
)
from mcp_server.application.agents.socratic.state import SocraticTutorState
from mcp_server.application.llm import get_chat_model
from mcp_server.application.llm_model_name import resolve_invoked_model_name
from mcp_server.application.tutor_session_draft import (
    DraftPatchThrottle,
    patch_tutor_session_draft_fail_open,
)
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.llm_routing import LLMComplexity
from mcp_server.domain.socratic import (
    SocraticCatalogPort,
    SocraticReply,
    normalize_locale,
    tutor_turn_index,
    validate_socratic_reply,
)
from mcp_server.domain.tutor_session_draft import TutorSessionDraftPort

_catalog: SocraticCatalogPort | None = None
_draft_port: TutorSessionDraftPort | None = None


def register_socratic_catalog(port: SocraticCatalogPort) -> None:
    global _catalog
    _catalog = port


def register_tutor_session_draft(port: TutorSessionDraftPort | None) -> None:
    global _draft_port
    _draft_port = port


def _require_catalog() -> SocraticCatalogPort:
    if _catalog is None:
        raise ResourceNotFoundError("Socratic catalog port not initialized")
    return _catalog


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


async def ground_context(state: SocraticTutorState) -> dict[str, Any]:
    """Catalog/graph grounding only — RAG embeddings are backend-owned, never MCP."""
    existing = state.get("grounding")
    if existing is not None:
        return {"grounding": existing, "error": None}

    catalog = _require_catalog()
    grounding = catalog.load_grounding(
        tenant_id=state["tenant_id"],
        course_slug=state["course_slug"],
        module_slug=state.get("module_slug"),
        lesson_slug=state.get("lesson_slug"),
        project_slug=state.get("project_slug"),
        query=state["message"],
    )
    # Explicitly keep documents empty — no retrieve_with_videos / ONNX on MCP.
    grounding.documents = []
    return {"grounding": grounding, "error": None}


async def generate_reply(state: SocraticTutorState) -> dict[str, Any]:
    model = get_chat_model()
    if model is None:
        raise ResourceNotFoundError("Chat model has not been initialized")

    locale = normalize_locale(state.get("locale"))
    hint_level = int(state.get("hint_level") or 1)
    want_full = bool(state.get("want_full_solution"))
    grounding = state.get("grounding")

    messages = [
        SystemMessage(
            content=socratic_system_prompt(
                locale=locale,
                hint_level=hint_level,
                want_full_solution=want_full,
            )
        ),
        HumanMessage(
            content=socratic_user_prompt(
                message=state["message"],
                history=list(state.get("history") or []),
                grounding=grounding,
                course_slug=state["course_slug"],
                module_slug=state.get("module_slug"),
                lesson_slug=state.get("lesson_slug"),
                project_slug=state.get("project_slug"),
            )
        ),
    ]
    session_id = str(state.get("session_id") or "").strip() or None
    try:
        if session_id:
            await patch_tutor_session_draft_fail_open(
                _draft_port,
                session_id=session_id,
                draft_reply=None,
            )
            accumulated = ""
            throttle = DraftPatchThrottle()
            async for chunk in model.astream(
                messages,
                llm_complexity=int(LLMComplexity.MEDIUM),
            ):
                piece = _message_content(getattr(chunk, "content", ""))
                if not piece:
                    continue
                accumulated += piece
                if throttle.should_flush(accumulated):
                    await patch_tutor_session_draft_fail_open(
                        _draft_port,
                        session_id=session_id,
                        draft_reply=accumulated,
                    )
                    throttle.mark_flushed(accumulated)
            if accumulated and throttle.should_flush(accumulated, force=True):
                await patch_tutor_session_draft_fail_open(
                    _draft_port,
                    session_id=session_id,
                    draft_reply=accumulated,
                )
                throttle.mark_flushed(accumulated)
            text = accumulated.strip()
        else:
            response = await model.ainvoke(
                messages,
                llm_complexity=int(LLMComplexity.MEDIUM),
            )
            text = _message_content(response.content).strip()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"llm_failed:{exc}", "reply": None}

    return {
        "reply": text,
        "model_id": resolve_invoked_model_name(model),
        "validation_errors": [],
        "error": None,
    }


async def validate_reply(state: SocraticTutorState) -> dict[str, Any]:
    reply = state.get("reply")
    retries = int(state.get("reply_retry_count") or 0)
    want_full = bool(state.get("want_full_solution"))
    if not reply:
        return {"validation_errors": ["missing_reply"], "reply_retry_count": retries}
    check = validate_socratic_reply(
        reply,
        asked_full_solution=want_full,
        turn_index=tutor_turn_index(state.get("history")),
    )
    if not check["ok"]:
        return {
            "validation_errors": list(check["errors"]),
            "reply_retry_count": retries + 1,
        }
    grounding = state.get("grounding")
    used = bool(
        grounding
        and (
            grounding.lesson_markdown
            or grounding.project_readme
            or grounding.graph_hits
            or grounding.documents
        )
    )
    return {
        "validation_errors": [],
        "reply_retry_count": retries,
        "result": SocraticReply(
            reply=reply,
            hint_level=int(state.get("hint_level") or 1),
            locale=normalize_locale(state.get("locale")),
            asked_full_solution=want_full,
            grounding_used=used,
        ),
    }
