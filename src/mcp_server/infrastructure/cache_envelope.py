"""Typed serialization envelopes for cache payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


def _to_json_compatible(value: Any) -> Any:
    """Normalize values for JSON-compatible Pydantic serialization."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_to_json_compatible(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    return value


class McpToolCacheEnvelope(BaseModel):
    """Pydantic envelope for MCP tool cache round-trips."""

    model_config = ConfigDict(extra="forbid")

    result: Any

    @classmethod
    def pack(cls, result: Any) -> bytes:
        """Serialize a tool result into cache bytes."""
        envelope = cls(result=_to_json_compatible(result))
        return envelope.model_dump_json().encode("utf-8")

    @classmethod
    def unpack(cls, payload: bytes) -> Any:
        """Deserialize cache bytes into a tool result."""
        return cls.model_validate_json(payload).result
