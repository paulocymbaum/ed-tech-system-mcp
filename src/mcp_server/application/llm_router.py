"""LLM routing orchestration: complexity mapping, fallback, and error handling."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import SecretStr

from mcp_server.domain.llm_routing import (
    IGroqModelRegistry,
    ILLMDebounceGate,
    LLMComplexity,
    token_limit_deactivation_until,
)

GroqChatModelBuilder = Callable[[SecretStr, str, float], BaseChatModel]

TOKEN_LIMIT_COOLDOWN_SECONDS = 3 * 60 * 60


def is_token_limit_error(exc: BaseException) -> bool:
    """Return whether an exception indicates a provider token/context limit."""
    message = str(exc).lower()
    if "context_length" in message:
        return True
    if "maximum context" in message:
        return True
    if "token" in message and "limit" in message:
        return True
    if "too many tokens" in message:
        return True

    error_code = getattr(exc, "code", None)
    if isinstance(error_code, str) and "context_length" in error_code.lower():
        return True

    status_code = getattr(exc, "status_code", None)
    return status_code == 413


def model_capability_score(model_id: str) -> int:
    """Estimate relative model capability for routing (higher = more capable)."""
    lowered = model_id.lower()
    if "mixtral" in lowered:
        return 45
    if "120b" in lowered:
        return 120
    if "70b" in lowered:
        return 70
    if "32b" in lowered or "20b" in lowered:
        return 32
    if "scout" in lowered:
        return 17
    numbers = [int(match) for match in re.findall(r"(\d+)b", lowered)]
    if numbers:
        return max(numbers)
    if "8b" in lowered or "9b" in lowered:
        return 8
    return 10


class LLMRouter:
    """Select Groq models by complexity and execute with debounce and fallback."""

    def __init__(
        self,
        *,
        api_key: SecretStr,
        temperature: float,
        registry: IGroqModelRegistry,
        debounce_gate: ILLMDebounceGate,
        model_builder: GroqChatModelBuilder,
        default_complexity: LLMComplexity = LLMComplexity.MEDIUM,
        token_limit_cooldown_seconds: float = TOKEN_LIMIT_COOLDOWN_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._temperature = temperature
        self._registry = registry
        self._debounce_gate = debounce_gate
        self._model_builder = model_builder
        self._default_complexity = default_complexity
        self._token_limit_cooldown_seconds = token_limit_cooldown_seconds
        self._model_cache: dict[str, BaseChatModel] = {}
        self._last_used_model_id: str | None = None

    @property
    def last_used_model_id(self) -> str | None:
        """Return the Groq model id that served the most recent successful completion."""
        return self._last_used_model_id

    def refresh_registry(self) -> None:
        self._registry.refresh_from_catalog()

    def set_temperature(self, temperature: float) -> None:
        """Update the default sampling temperature for built models."""
        self._temperature = temperature

    def candidate_model_ids(
        self,
        complexity: LLMComplexity,
        *,
        preferred_model_id: str | None = None,
    ) -> list[str]:
        active_ids = self._registry.get_active_model_ids()
        if not active_ids:
            self.refresh_registry()
            active_ids = self._registry.get_active_model_ids()

        ranked = sorted(active_ids, key=model_capability_score)
        if not ranked:
            if preferred_model_id:
                return [preferred_model_id]
            msg = "No active Groq models available for routing"
            raise RuntimeError(msg)

        tier_index = {
            LLMComplexity.LOW: 0,
            LLMComplexity.MEDIUM: max(0, len(ranked) // 2),
            LLMComplexity.HIGH: len(ranked) - 1,
        }[complexity]
        primary = ranked[tier_index]

        fallback_chain = [primary]
        for model_id in ranked:
            if model_id not in fallback_chain:
                fallback_chain.append(model_id)

        if preferred_model_id and preferred_model_id not in fallback_chain:
            fallback_chain.insert(0, preferred_model_id)
        elif preferred_model_id and preferred_model_id in fallback_chain:
            fallback_chain.remove(preferred_model_id)
            fallback_chain.insert(0, preferred_model_id)

        return fallback_chain

    def generate(
        self,
        messages: list[BaseMessage],
        *,
        complexity: LLMComplexity | None = None,
        preferred_model_id: str | None = None,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._debounce_gate.acquire_sync()
        resolved_complexity = complexity or self._default_complexity
        last_error: BaseException | None = None

        for model_id in self.candidate_model_ids(
            resolved_complexity,
            preferred_model_id=preferred_model_id,
        ):
            try:
                model = self._get_or_build_model(model_id)
                result = model._generate(
                    messages,
                    stop=stop,
                    run_manager=run_manager,
                    **kwargs,
                )
                self._last_used_model_id = model_id
                return result
            except Exception as exc:  # noqa: BLE001 — fallback boundary
                last_error = exc
                if is_token_limit_error(exc):
                    self._registry.deactivate_until(
                        model_id,
                        token_limit_deactivation_until(),
                    )
                continue

        if last_error is not None:
            raise last_error
        msg = "LLM routing failed without a provider error"
        raise RuntimeError(msg)

    async def agenerate(
        self,
        messages: list[BaseMessage],
        *,
        complexity: LLMComplexity | None = None,
        preferred_model_id: str | None = None,
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        await self._debounce_gate.acquire()
        resolved_complexity = complexity or self._default_complexity
        last_error: BaseException | None = None

        for model_id in self.candidate_model_ids(
            resolved_complexity,
            preferred_model_id=preferred_model_id,
        ):
            try:
                model = self._get_or_build_model(model_id)
                result = await model._agenerate(
                    messages,
                    stop=stop,
                    run_manager=run_manager,
                    **kwargs,
                )
                self._last_used_model_id = model_id
                return result
            except Exception as exc:  # noqa: BLE001 — fallback boundary
                last_error = exc
                if is_token_limit_error(exc):
                    self._registry.deactivate_until(
                        model_id,
                        token_limit_deactivation_until(),
                    )
                continue

        if last_error is not None:
            raise last_error
        msg = "LLM routing failed without a provider error"
        raise RuntimeError(msg)

    def _get_or_build_model(self, model_id: str) -> BaseChatModel:
        cached = self._model_cache.get(model_id)
        if cached is not None:
            return cached
        built = self._model_builder(self._api_key, model_id, self._temperature)
        self._model_cache[model_id] = built
        return built
