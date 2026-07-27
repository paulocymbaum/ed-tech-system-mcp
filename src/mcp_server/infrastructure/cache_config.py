"""Map entrypoint settings to domain cache rules."""

from __future__ import annotations

from typing import Protocol

from mcp_server.domain.cache import (
    DEFAULT_CACHE_RULES,
    CacheOperationType,
    CacheRule,
    CacheRuleSet,
)


class CacheSettings(Protocol):
    """Subset of Settings required to build cache rules."""

    cache_enabled: bool
    cache_ttl_supabase_find_documents: int | None
    cache_ttl_youtube_search_videos: int | None
    cache_ttl_web_search: int | None
    cache_ttl_mcp_tool: int | None
    cache_ttl_llm_completion: int | None
    cache_key_prefix_supabase: str | None
    cache_key_prefix_youtube: str | None
    cache_key_prefix_web: str | None
    cache_key_prefix_mcp_tool: str | None
    cache_key_prefix_llm: str | None
    cache_ttl_embedding_query: int | None
    cache_ttl_vector_retrieve: int | None
    cache_key_prefix_embedding: str | None
    cache_key_prefix_vector: str | None


_TTL_OVERRIDES: dict[CacheOperationType, str] = {
    CacheOperationType.SUPABASE_FIND_DOCUMENTS: "cache_ttl_supabase_find_documents",
    CacheOperationType.YOUTUBE_SEARCH_VIDEOS: "cache_ttl_youtube_search_videos",
    CacheOperationType.WEB_SEARCH: "cache_ttl_web_search",
    CacheOperationType.MCP_TOOL: "cache_ttl_mcp_tool",
    CacheOperationType.LLM_COMPLETION: "cache_ttl_llm_completion",
    CacheOperationType.EMBEDDING_QUERY: "cache_ttl_embedding_query",
    CacheOperationType.VECTOR_RETRIEVE: "cache_ttl_vector_retrieve",
}

_PREFIX_OVERRIDES: dict[CacheOperationType, str] = {
    CacheOperationType.SUPABASE_FIND_DOCUMENTS: "cache_key_prefix_supabase",
    CacheOperationType.YOUTUBE_SEARCH_VIDEOS: "cache_key_prefix_youtube",
    CacheOperationType.WEB_SEARCH: "cache_key_prefix_web",
    CacheOperationType.MCP_TOOL: "cache_key_prefix_mcp_tool",
    CacheOperationType.LLM_COMPLETION: "cache_key_prefix_llm",
    CacheOperationType.EMBEDDING_QUERY: "cache_key_prefix_embedding",
    CacheOperationType.VECTOR_RETRIEVE: "cache_key_prefix_vector",
}


def build_cache_rule_set(settings: CacheSettings) -> CacheRuleSet:
    """Build cache rules from settings, applying TTL and prefix overrides."""
    rules: dict[CacheOperationType, CacheRule] = {}
    for operation, default_rule in DEFAULT_CACHE_RULES.items():
        ttl_override = getattr(settings, _TTL_OVERRIDES[operation])
        prefix_override = getattr(settings, _PREFIX_OVERRIDES[operation])
        rules[operation] = default_rule.model_copy(
            update={
                "enabled": settings.cache_enabled,
                "ttl_seconds": (
                    ttl_override if ttl_override is not None else default_rule.ttl_seconds
                ),
                "key_prefix": prefix_override if prefix_override else default_rule.key_prefix,
            }
        )
    return CacheRuleSet(rules=rules)
