"""Groq chat model adapter for LangChain."""

from __future__ import annotations

from langchain_groq import ChatGroq
from pydantic import SecretStr


def build_groq_chat_model(
    *,
    api_key: SecretStr,
    model_id: str,
    temperature: float,
) -> ChatGroq:
    """Build a Groq-backed LangChain chat model."""
    return ChatGroq(
        api_key=api_key,
        model=model_id,
        temperature=temperature,
    )
