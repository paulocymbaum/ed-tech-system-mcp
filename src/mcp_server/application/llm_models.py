"""Registry of language models available to agent workflows."""

from __future__ import annotations

from typing import TypedDict

from mcp_server.domain.llm_routing import GroqModelRecord


class LanguageModelSpec(TypedDict):
    """Metadata for a supported chat model."""

    id: str
    provider: str
    display_name: str


_STATIC_LANGUAGE_MODELS: list[LanguageModelSpec] = [
    {
        "id": "gpt-4o",
        "provider": "openai",
        "display_name": "GPT-4o",
    },
    {
        "id": "gpt-4o-mini",
        "provider": "openai",
        "display_name": "GPT-4o Mini",
    },
    {
        "id": "gpt-4.1",
        "provider": "openai",
        "display_name": "GPT-4.1",
    },
    {
        "id": "gpt-4.1-mini",
        "provider": "openai",
        "display_name": "GPT-4.1 Mini",
    },
    {
        "id": "claude-sonnet-4-20250514",
        "provider": "anthropic",
        "display_name": "Claude Sonnet 4",
    },
    {
        "id": "claude-3-5-haiku-20241022",
        "provider": "anthropic",
        "display_name": "Claude 3.5 Haiku",
    },
]

_GROQ_LANGUAGE_MODELS: list[LanguageModelSpec] = []

AVAILABLE_LANGUAGE_MODELS: list[LanguageModelSpec] = [
    *_STATIC_LANGUAGE_MODELS,
]


def register_groq_language_models(records: list[GroqModelRecord]) -> None:
    """Replace Groq entries with active models from the backend allowlist registry."""
    global _GROQ_LANGUAGE_MODELS, AVAILABLE_LANGUAGE_MODELS
    _GROQ_LANGUAGE_MODELS = [
        {
            "id": record.model_id,
            "provider": "groq",
            "display_name": record.display_name or record.model_id,
        }
        for record in records
        if record.active and record.is_routable
    ]
    AVAILABLE_LANGUAGE_MODELS = [*_GROQ_LANGUAGE_MODELS, *_STATIC_LANGUAGE_MODELS]


def reset_groq_language_models() -> None:
    """Clear dynamically registered Groq models (for tests)."""
    global _GROQ_LANGUAGE_MODELS, AVAILABLE_LANGUAGE_MODELS
    _GROQ_LANGUAGE_MODELS = []
    AVAILABLE_LANGUAGE_MODELS = [*_STATIC_LANGUAGE_MODELS]


def list_available_language_models() -> list[LanguageModelSpec]:
    """Return static and Groq catalog-backed language model metadata."""
    return list(AVAILABLE_LANGUAGE_MODELS)


def resolve_language_model(model_id: str) -> LanguageModelSpec:
    """Return registry metadata for a model id."""
    for model in list_available_language_models():
        if model["id"] == model_id:
            return model
    msg = f"Unknown language model id: {model_id}"
    raise ValueError(msg)
