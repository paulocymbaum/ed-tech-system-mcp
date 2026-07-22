"""Parse and validate structured JSON from LLM completions."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


def extract_json_object(text: str) -> dict[str, object]:
    """Extract a JSON object from raw LLM text, tolerating fenced code blocks."""
    stripped = text.strip()
    fence_match = _JSON_FENCE_RE.match(stripped)
    if fence_match is not None:
        stripped = fence_match.group(1).strip()
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        msg = "LLM output must be a JSON object"
        raise TypeError(msg)
    return payload


def parse_structured_output[TModel: BaseModel](text: str, model: type[TModel]) -> TModel:
    """Parse LLM text into a validated Pydantic model."""
    payload = extract_json_object(text)
    return model.model_validate(payload)


def validation_error_messages(exc: ValidationError) -> list[str]:
    """Flatten Pydantic validation errors for retry feedback."""
    return [
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
        for error in exc.errors()
    ]
