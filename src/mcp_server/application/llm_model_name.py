"""Resolve the provider model name from a LangChain chat model instance."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel


def resolve_invoked_model_name(model: BaseChatModel) -> str:
    """Return the model id used for the latest completion, when available."""
    target: BaseChatModel = model
    inner = getattr(target, "_inner", None)
    if isinstance(inner, BaseChatModel):
        target = inner

    last_used = getattr(target, "last_used_model_id", None)
    if last_used is not None and not callable(last_used) and isinstance(last_used, str):
        return last_used
    if callable(last_used):
        resolved = last_used()
        if isinstance(resolved, str) and resolved:
            return resolved

    model_id = getattr(target, "model_id", None)
    if isinstance(model_id, str) and model_id:
        return model_id

    llm_type = getattr(target, "_llm_type", None)
    if isinstance(llm_type, str) and llm_type:
        return llm_type

    return "unknown"
