"""tiktoken-backed token counter for LLM observability."""

from __future__ import annotations

import tiktoken

from mcp_server.domain.token_counting import ITokenCounter

_DEFAULT_ENCODING = "cl100k_base"
_MODEL_ENCODING_HINTS: dict[str, str] = {
    "gpt-4": "cl100k_base",
    "gpt-3.5": "cl100k_base",
    "llama": "cl100k_base",
    "mixtral": "cl100k_base",
    "gemma": "cl100k_base",
}


def resolve_encoding_name(model_name: str | None) -> str:
    """Map a provider model id to a tiktoken encoding name."""
    if not model_name:
        return _DEFAULT_ENCODING
    lowered = model_name.lower()
    for prefix, encoding in _MODEL_ENCODING_HINTS.items():
        if prefix in lowered:
            return encoding
    return _DEFAULT_ENCODING


class TiktokenTokenCounter(ITokenCounter):
    """Estimate token counts using tiktoken encodings."""

    def __init__(self, *, default_encoding: str = _DEFAULT_ENCODING) -> None:
        self._default_encoding = default_encoding
        self._encodings: dict[str, tiktoken.Encoding] = {}

    def _encoding_for_model(self, model_name: str | None) -> tiktoken.Encoding:
        name = resolve_encoding_name(model_name) if model_name else self._default_encoding
        cached = self._encodings.get(name)
        if cached is not None:
            return cached
        encoding = tiktoken.get_encoding(name)
        self._encodings[name] = encoding
        return encoding

    def count(self, text: str, *, model_name: str | None = None) -> int:
        if not text:
            return 0
        encoding = self._encoding_for_model(model_name)
        return len(encoding.encode(text))
