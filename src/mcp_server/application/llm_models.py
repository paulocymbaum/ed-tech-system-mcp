"""Registry of language models available to agent workflows."""

from __future__ import annotations

from typing import TypedDict


class LanguageModelSpec(TypedDict):
    """Metadata for a supported chat model."""

    id: str
    provider: str
    display_name: str


AVAILABLE_LANGUAGE_MODELS: list[LanguageModelSpec] = [
    {
        "id": "llama-3.3-70b-versatile",
        "provider": "groq",
        "display_name": "Llama 3.3 70B Versatile",
    },
    {
        "id": "llama-3.1-8b-instant",
        "provider": "groq",
        "display_name": "Llama 3.1 8B Instant",
    },
    {
        "id": "llama-3.1-70b-versatile",
        "provider": "groq",
        "display_name": "Llama 3.1 70B Versatile",
    },
    {
        "id": "mixtral-8x7b-32768",
        "provider": "groq",
        "display_name": "Mixtral 8x7B",
    },
    {
        "id": "gemma2-9b-it",
        "provider": "groq",
        "display_name": "Gemma 2 9B IT",
    },
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


def resolve_language_model(model_id: str) -> LanguageModelSpec:
    """Return registry metadata for a model id."""
    for model in AVAILABLE_LANGUAGE_MODELS:
        if model["id"] == model_id:
            return model
    msg = f"Unknown language model id: {model_id}"
    raise ValueError(msg)
