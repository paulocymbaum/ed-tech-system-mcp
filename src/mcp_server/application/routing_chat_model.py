"""LangChain chat model that routes Groq calls through LLMRouter."""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import PrivateAttr

from mcp_server.application.llm_router import LLMRouter
from mcp_server.domain.llm_routing import LLMComplexity


class RoutingChatModel(BaseChatModel):
    """Application-layer adapter that delegates all completions to the LLM router."""

    _router: LLMRouter = PrivateAttr()
    _default_complexity: LLMComplexity = PrivateAttr()
    _preferred_model_id: str | None = PrivateAttr()

    def __init__(
        self,
        router: LLMRouter,
        *,
        default_complexity: LLMComplexity = LLMComplexity.MEDIUM,
        preferred_model_id: str | None = None,
    ) -> None:
        super().__init__()
        self._router = router
        self._default_complexity = default_complexity
        self._preferred_model_id = preferred_model_id

    @property
    def last_used_model_id(self) -> str | None:
        """Return the Groq model id that served the most recent routed completion."""
        return self._router.last_used_model_id

    @property
    def _llm_type(self) -> str:
        return "routing-groq"

    def _resolve_complexity(self, kwargs: dict[str, Any]) -> LLMComplexity:
        raw = kwargs.pop("llm_complexity", None)
        if raw is None:
            return self._default_complexity
        return LLMComplexity(int(raw))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        complexity = self._resolve_complexity(kwargs)
        return self._router.generate(
            messages,
            complexity=complexity,
            preferred_model_id=self._preferred_model_id,
            stop=stop,
            run_manager=run_manager,
            **kwargs,
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        complexity = self._resolve_complexity(kwargs)
        return await self._router.agenerate(
            messages,
            complexity=complexity,
            preferred_model_id=self._preferred_model_id,
            stop=stop,
            run_manager=run_manager,
            **kwargs,
        )
