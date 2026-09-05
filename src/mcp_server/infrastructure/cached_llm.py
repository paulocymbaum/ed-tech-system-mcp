"""Cache-aside wrapper for LangChain chat models."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import PrivateAttr

from mcp_server.domain.cache import (
    CacheOperationType,
    CacheRuleSet,
    ICacheStore,
    build_cache_key,
)
from mcp_server.infrastructure.cache_aside import run_cache_aside
from mcp_server.infrastructure.port_observability import PortCallSpan


def _serialize_chat_result(result: ChatResult) -> bytes:
    generations = [
        {
            "message": generation.message.model_dump(),
            "generation_info": generation.generation_info,
        }
        for generation in result.generations
    ]
    return json.dumps(
        {
            "generations": generations,
            "llm_output": result.llm_output,
        }
    ).encode("utf-8")


def _deserialize_chat_result(payload: bytes) -> ChatResult:
    raw = json.loads(payload.decode("utf-8"))
    generations = [
        ChatGeneration(
            message=BaseMessage(**item["message"]),
            generation_info=item.get("generation_info"),
        )
        for item in raw["generations"]
    ]
    return ChatResult(generations=generations, llm_output=raw.get("llm_output"))


def _message_payload(messages: Sequence[BaseMessage], kwargs: dict[str, Any]) -> dict[str, Any]:
    return {
        "messages": [message.model_dump() for message in messages],
        "kwargs": kwargs,
    }


class CachedChatModel(BaseChatModel):
    """Cache-aside wrapper for chat model completions (async path only).

    Cache reads and writes occur in ``_agenerate`` (used by ``ainvoke`` and
    LangGraph async nodes). ``_generate`` delegates directly to the inner model
    with no cache lookup or store — sync callers always hit the provider.

    ``_astream`` also skips cache (JB-012 / OQ-009): token streams must not
    collapse to one cached ``_agenerate`` blob. JSON ``ainvoke`` keeps cache.

    Add sync caching only when a production caller uses the sync path; until
    then, defer to avoid duplicate key logic and untested code paths.
    """

    _inner: BaseChatModel = PrivateAttr()
    _cache: ICacheStore = PrivateAttr()
    _rules: CacheRuleSet = PrivateAttr()
    _model_name: str = PrivateAttr()

    def __init__(
        self,
        inner: BaseChatModel,
        cache: ICacheStore,
        rules: CacheRuleSet,
        *,
        model_name: str,
    ) -> None:
        super().__init__()
        self._inner = inner
        self._cache = cache
        self._rules = rules
        self._model_name = model_name

    @property
    def _llm_type(self) -> str:
        return f"cached-{self._inner._llm_type}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._inner._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        operation = CacheOperationType.LLM_COMPLETION
        rule = self._rules.for_operation(operation)
        if rule is None or not rule.enabled:
            return await self._inner._agenerate(
                messages,
                stop=stop,
                run_manager=run_manager,
                **kwargs,
            )

        cache_params = {
            "model": self._model_name,
            **_message_payload(messages, kwargs),
        }
        key = build_cache_key(operation, cache_params, prefix=rule.key_prefix)

        async def loader() -> ChatResult:
            return await self._inner._agenerate(
                messages,
                stop=stop,
                run_manager=run_manager,
                **kwargs,
            )

        return await run_cache_aside(
            cache=self._cache,
            key=key,
            rule=rule,
            operation=operation.value,
            span=PortCallSpan("llm_completion"),
            serialize=_serialize_chat_result,
            deserialize=_deserialize_chat_result,
            loader=loader,
        )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Token stream: delegate to the inner model with no cache lookup/store."""
        if type(self._inner)._astream is not BaseChatModel._astream:
            async for chunk in self._inner._astream(
                messages,
                stop=stop,
                run_manager=run_manager,
                **kwargs,
            ):
                yield chunk
            return
        async for message in self._inner.astream(messages, stop=stop, **kwargs):
            yield ChatGenerationChunk(message=message)
