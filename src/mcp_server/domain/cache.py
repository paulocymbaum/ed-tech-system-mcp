"""Cache port, rules, and deterministic key-generation contracts."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CacheOperationType(StrEnum):
    """Supported cacheable operation identifiers."""

    SUPABASE_FIND_DOCUMENTS = "supabase.find_documents"
    YOUTUBE_SEARCH_VIDEOS = "youtube.search_videos"
    WEB_SEARCH = "web.search"
    MCP_TOOL = "mcp.tool"
    LLM_COMPLETION = "llm.completion"
    EMBEDDING_QUERY = "embedding.query"
    VECTOR_RETRIEVE = "vector.retrieve"


class CacheRule(BaseModel):
    """Per-operation cache policy."""

    operation: CacheOperationType
    enabled: bool = True
    ttl_seconds: int = Field(default=300, ge=0)
    key_prefix: str = ""


class CacheRuleSet(BaseModel):
    """Collection of cache rules keyed by operation type."""

    rules: dict[CacheOperationType, CacheRule] = Field(default_factory=dict)

    def for_operation(self, operation: CacheOperationType) -> CacheRule | None:
        """Return the rule for an operation, if configured."""
        return self.rules.get(operation)

    def is_enabled(self, operation: CacheOperationType) -> bool:
        """Return whether caching is enabled for the operation."""
        rule = self.for_operation(operation)
        return rule is not None and rule.enabled


# Redis cache-aside for RAG retrieval is intentionally disabled at the MCP layer.
# Chunk freshness and any retrieval caching belong in Supabase/pgvector (backend).
# ONNX embedding model weights use ``EMBEDDING_CACHE_DIR`` (image bake), not Redis.
RAG_REDIS_CACHE_OPERATIONS: frozenset[CacheOperationType] = frozenset(
    {
        CacheOperationType.SUPABASE_FIND_DOCUMENTS,
        CacheOperationType.EMBEDDING_QUERY,
        CacheOperationType.VECTOR_RETRIEVE,
    }
)

DEFAULT_CACHE_RULES: dict[CacheOperationType, CacheRule] = {
    CacheOperationType.SUPABASE_FIND_DOCUMENTS: CacheRule(
        operation=CacheOperationType.SUPABASE_FIND_DOCUMENTS,
        ttl_seconds=600,
        key_prefix="supabase",
    ),
    CacheOperationType.YOUTUBE_SEARCH_VIDEOS: CacheRule(
        operation=CacheOperationType.YOUTUBE_SEARCH_VIDEOS,
        ttl_seconds=3600,
        key_prefix="youtube",
    ),
    CacheOperationType.WEB_SEARCH: CacheRule(
        operation=CacheOperationType.WEB_SEARCH,
        ttl_seconds=300,
        key_prefix="web",
    ),
    CacheOperationType.MCP_TOOL: CacheRule(
        operation=CacheOperationType.MCP_TOOL,
        ttl_seconds=60,
        key_prefix="mcp",
    ),
    CacheOperationType.LLM_COMPLETION: CacheRule(
        operation=CacheOperationType.LLM_COMPLETION,
        ttl_seconds=3600,
        key_prefix="llm",
    ),
    CacheOperationType.EMBEDDING_QUERY: CacheRule(
        operation=CacheOperationType.EMBEDDING_QUERY,
        ttl_seconds=3600,
        key_prefix="embed",
    ),
    CacheOperationType.VECTOR_RETRIEVE: CacheRule(
        operation=CacheOperationType.VECTOR_RETRIEVE,
        ttl_seconds=600,
        key_prefix="vector",
    ),
}


class ICacheStore(ABC):
    """Port for ephemeral key-value cache storage."""

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Return cached bytes for key, or None on miss."""

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl_seconds: int) -> None:
        """Store bytes under key with a time-to-live in seconds."""


def _canonicalize(value: Any) -> Any:
    """Normalize values for stable cache-key serialization."""
    if isinstance(value, dict):
        return {
            str(k): _canonicalize(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)) or value is None:
        return value
    return str(value)


def build_cache_key(
    operation: CacheOperationType,
    params: dict[str, Any],
    *,
    prefix: str = "",
) -> str:
    """Build a deterministic cache key from an operation and normalized parameters."""
    canonical = _canonicalize(params)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    namespace = prefix.strip() or operation.value
    return f"{namespace}:{digest}"
