"""JB-012 / OQ-009: CachedChatModel token stream skips cache; ainvoke may cache."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from mcp_server.domain.cache import DEFAULT_CACHE_RULES, CacheRuleSet, ICacheStore
from mcp_server.infrastructure.cached_llm import CachedChatModel


class CountingCache(ICacheStore):
    def __init__(self) -> None:
        self.gets = 0
        self.sets = 0
        self._data: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        self.gets += 1
        return self._data.get(key)

    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        self.sets += 1
        self._data[key] = value


class _InnerModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "inner-stub"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="full"))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        _INNER_COUNTS["agenerate"] += 1
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        _INNER_COUNTS["astream"] += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content="tok"))


_INNER_COUNTS: dict[str, int] = {"agenerate": 0, "astream": 0}


def _wrapped() -> tuple[CachedChatModel, CountingCache]:
    _INNER_COUNTS["agenerate"] = 0
    _INNER_COUNTS["astream"] = 0
    cache = CountingCache()
    inner = _InnerModel()
    rules = CacheRuleSet(rules=dict(DEFAULT_CACHE_RULES))
    model = CachedChatModel(inner, cache, rules, model_name="routing-groq")
    return model, cache


@pytest.mark.asyncio
async def test_astream_does_not_hit_or_store_cache() -> None:
    model, cache = _wrapped()
    chunks: list[ChatGenerationChunk] = []
    async for chunk in model._astream([HumanMessage(content="hi")]):
        chunks.append(chunk)
    assert [c.message.content for c in chunks] == ["tok"]
    assert _INNER_COUNTS["astream"] == 1
    assert _INNER_COUNTS["agenerate"] == 0
    assert cache.gets == 0
    assert cache.sets == 0


@pytest.mark.asyncio
async def test_agenerate_still_uses_cache() -> None:
    model, cache = _wrapped()
    messages = [HumanMessage(content="hi")]
    first = await model._agenerate(messages)
    second = await model._agenerate(messages)
    assert first.generations[0].message.content == "full"
    assert second.generations[0].message.content == "full"
    assert _INNER_COUNTS["agenerate"] == 1
    assert cache.gets >= 1
    assert cache.sets == 1
