"""JB-012: draft throttle, generate_reply stream vs ainvoke, tool cache bypass."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

from mcp_server.application.agents.socratic.nodes import (
    generate_reply,
    register_tutor_session_draft,
)
from mcp_server.application.tutor_session_draft import (
    DRAFT_PATCH_EVERY_N_CHARS,
    DraftPatchThrottle,
    patch_tutor_session_draft_fail_open,
)
from mcp_server.domain.socratic import SocraticReply
from mcp_server.domain.tutor_session_draft import TutorSessionDraftPort
from mcp_server.interface.custom_tools_socratic import socratic_tutor

_SESSION = "00000000-0000-4000-8000-000000000012"


class FakeDraftPort(TutorSessionDraftPort):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    async def patch(self, *, session_id: str, draft_reply: str | None) -> None:
        self.calls.append((session_id, draft_reply))


class _StreamingModel:
    def __init__(self) -> None:
        self.ainvoke_calls = 0
        self.astream_calls = 0

    async def ainvoke(self, _messages: object, **_kwargs: object) -> AIMessage:
        self.ainvoke_calls += 1
        return AIMessage(content="Why try a smaller step?")

    async def astream(self, _messages: object, **_kwargs: object):
        self.astream_calls += 1
        for part in ("Why ", "try?"):
            yield AIMessageChunk(content=part)


def _base_state(**extra: object) -> dict[str, Any]:
    state: dict[str, Any] = {
        "tenant_id": "t",
        "course_slug": "js",
        "message": "help",
        "history": [],
        "hint_level": 1,
        "locale": "en",
        "want_full_solution": False,
        "grounding": None,
    }
    state.update(extra)
    return state


def test_draft_patch_every_n_chars_is_documented_window() -> None:
    assert 24 <= DRAFT_PATCH_EVERY_N_CHARS <= 40


def test_throttle_first_token_then_n_chars() -> None:
    throttle = DraftPatchThrottle()
    assert throttle.should_flush("W")
    throttle.mark_flushed("W")
    assert throttle.should_flush("Wx") is False
    grown = "W" + ("x" * DRAFT_PATCH_EVERY_N_CHARS)
    assert throttle.should_flush(grown)
    assert throttle.should_flush("Wx", force=True)


@pytest.mark.asyncio
async def test_patch_fail_open_when_port_raises() -> None:
    class Boom(TutorSessionDraftPort):
        async def patch(self, *, session_id: str, draft_reply: str | None) -> None:
            raise RuntimeError("rpc down")

    await patch_tutor_session_draft_fail_open(
        Boom(),
        session_id=_SESSION,
        draft_reply="hi",
    )


@pytest.mark.asyncio
async def test_generate_reply_omitted_session_uses_ainvoke_and_skips_patch() -> None:
    port = FakeDraftPort()
    register_tutor_session_draft(port)
    model = _StreamingModel()
    with patch(
        "mcp_server.application.agents.socratic.nodes.get_chat_model",
        return_value=model,
    ):
        result = await generate_reply(_base_state())
    assert result["reply"] == "Why try a smaller step?"
    assert model.ainvoke_calls == 1
    assert model.astream_calls == 0
    assert port.calls == []
    register_tutor_session_draft(None)


@pytest.mark.asyncio
async def test_generate_reply_with_session_streams_and_patches() -> None:
    port = FakeDraftPort()
    register_tutor_session_draft(port)
    model = _StreamingModel()
    with patch(
        "mcp_server.application.agents.socratic.nodes.get_chat_model",
        return_value=model,
    ):
        result = await generate_reply(_base_state(session_id=_SESSION))
    assert result["reply"] == "Why try?"
    assert model.astream_calls == 1
    assert model.ainvoke_calls == 0
    assert port.calls[0] == (_SESSION, None)
    assert port.calls[-1] == (_SESSION, "Why try?")
    register_tutor_session_draft(None)


def _tool_graph_patches(ainvoke: AsyncMock) -> tuple[Any, Any]:
    return (
        patch(
            "mcp_server.interface.custom_tools_socratic.get_socratic_tutor_graph",
            return_value=MagicMock(),
        ),
        patch(
            "mcp_server.interface.custom_tools_socratic.ainvoke_with_workflow_timeout",
            ainvoke,
        ),
    )


@pytest.mark.asyncio
async def test_socratic_tutor_omitted_session_uses_tool_cache() -> None:
    reply = SocraticReply(reply="Hint?", hint_level=1, locale="en")
    ainvoke = AsyncMock(return_value={"result": reply})

    async def passthrough(_name: str, _args: dict[str, object], invoker: Any) -> Any:
        return await invoker()

    cached = AsyncMock(side_effect=passthrough)
    graph_p, invoke_p = _tool_graph_patches(ainvoke)
    with graph_p, invoke_p, patch(
        "mcp_server.interface.custom_tools_socratic._cached_tool_invoke",
        cached,
    ):
        result = await socratic_tutor(
            tenant_id="t",
            course_slug="js",
            message="help me",
        )
    assert result.reply == "Hint?"
    cached.assert_awaited_once()
    state = ainvoke.await_args.args[1]
    assert not state.get("session_id")


@pytest.mark.asyncio
async def test_socratic_tutor_with_session_bypasses_tool_cache() -> None:
    reply = SocraticReply(reply="Hint?", hint_level=1, locale="en")
    ainvoke = AsyncMock(return_value={"result": reply})
    cached = AsyncMock()
    graph_p, invoke_p = _tool_graph_patches(ainvoke)
    with graph_p, invoke_p, patch(
        "mcp_server.interface.custom_tools_socratic._cached_tool_invoke",
        cached,
    ):
        result = await socratic_tutor(
            tenant_id="t",
            course_slug="js",
            message="help me",
            session_id=_SESSION,
        )
    assert result.reply == "Hint?"
    cached.assert_not_called()
    state = ainvoke.await_args.args[1]
    assert state["session_id"] == _SESSION
