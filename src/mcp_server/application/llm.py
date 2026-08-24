"""Chat model factory and runtime accessor."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import SecretStr

from mcp_server.application.llm_models import resolve_language_model
from mcp_server.application.llm_router import LLMRouter
from mcp_server.application.routing_chat_model import RoutingChatModel
from mcp_server.domain.cache import ICacheStore
from mcp_server.domain.llm_routing import LLMComplexity

GroqChatModelBuilder = Callable[[SecretStr, str, float], BaseChatModel]
ChatModelBuilder = Callable[["LLMSettings", ICacheStore | None], BaseChatModel]

_groq_model_builder: GroqChatModelBuilder | None = None
_llm_router: LLMRouter | None = None
_chat_model_builder: ChatModelBuilder | None = None
_lazy_settings: LLMSettings | None = None
_lazy_cache_store: ICacheStore | None = None
_runtime_chat_model: BaseChatModel | None = None


class LLMSettings(Protocol):
    """Settings subset required to build a chat model."""

    groq_api_key: SecretStr | None
    llm_temperature: float
    llm_complexity: int


def register_groq_model_builder(builder: GroqChatModelBuilder) -> None:
    """Register the infrastructure Groq adapter builder (composition root only)."""
    global _groq_model_builder
    _groq_model_builder = builder


def reset_groq_model_builder() -> None:
    """Clear the registered Groq builder (for tests)."""
    global _groq_model_builder
    _groq_model_builder = None


def register_llm_router(router: LLMRouter) -> None:
    """Register the wired LLM router (composition root only)."""
    global _llm_router
    _llm_router = router


def reset_llm_router() -> None:
    """Clear the registered LLM router (for tests)."""
    global _llm_router
    _llm_router = None


def register_chat_model_builder(builder: ChatModelBuilder) -> None:
    """Register the composition-root chat model builder (wiring only)."""
    global _chat_model_builder
    _chat_model_builder = builder


def reset_chat_model_builder() -> None:
    """Clear the registered chat model builder (for tests)."""
    global _chat_model_builder
    _chat_model_builder = None


def configure_lazy_chat_model(
    settings: LLMSettings | None,
    cache_store: ICacheStore | None = None,
) -> None:
    """Store settings and cache for deferred chat model construction at first access."""
    global _lazy_settings, _lazy_cache_store, _runtime_chat_model
    _lazy_settings = settings
    _lazy_cache_store = cache_store
    _runtime_chat_model = None


def set_chat_model(model: BaseChatModel | None) -> None:
    """Store the wired chat model for application consumers."""
    global _runtime_chat_model
    _runtime_chat_model = model


def get_chat_model() -> BaseChatModel | None:
    """Return the chat model, building lazily on first access when configured."""
    global _runtime_chat_model
    if _runtime_chat_model is not None:
        return _runtime_chat_model
    if _lazy_settings is None or _chat_model_builder is None:
        return None
    _runtime_chat_model = _chat_model_builder(_lazy_settings, _lazy_cache_store)
    return _runtime_chat_model


def reset_chat_model() -> None:
    """Clear the runtime chat model and lazy-init state (for tests)."""
    global _runtime_chat_model, _lazy_settings, _lazy_cache_store
    _runtime_chat_model = None
    _lazy_settings = None
    _lazy_cache_store = None


def create_chat_model(
    settings: LLMSettings,
    model_id: str | None = None,
    temperature: float | None = None,
) -> BaseChatModel:
    """Return a LangChain chat model that routes via the dynamic Groq allowlist.

    ``model_id`` is an explicit override (tests / rare callers). The default path
    does **not** pin ``LLM_MODEL`` from env — candidates come from
    ``list_active_groq_models`` by complexity tier.
    """
    resolved_temperature = settings.llm_temperature if temperature is None else temperature

    if settings.groq_api_key is None:
        msg = "GROQ_API_KEY is required for Groq language models"
        raise ValueError(msg)
    if _groq_model_builder is None:
        msg = "Groq model builder has not been registered"
        raise RuntimeError(msg)
    if _llm_router is None:
        msg = "LLM router has not been registered"
        raise RuntimeError(msg)

    preferred: str | None = None
    if model_id is not None:
        spec = resolve_language_model(model_id)
        if spec["provider"] != "groq":
            msg = f"Unsupported language model provider: {spec['provider']}"
            raise ValueError(msg)
        preferred = spec["id"]

    _llm_router.set_temperature(resolved_temperature)
    return RoutingChatModel(
        _llm_router,
        default_complexity=LLMComplexity(settings.llm_complexity),
        preferred_model_id=preferred,
    )
