"""Cache MCP tool interactions by normalized input/output payloads."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from mcp_server.domain.cache import (
    CacheOperationType,
    CacheRuleSet,
    ICacheStore,
    build_cache_key,
)
from mcp_server.infrastructure.cache_aside import run_cache_aside
from mcp_server.infrastructure.cache_envelope import McpToolCacheEnvelope
from mcp_server.infrastructure.port_observability import PortCallSpan

T = TypeVar("T")


class McpToolInteractionCache:
    """Cache-aside helper for MCP tool call input and output."""

    def __init__(self, cache: ICacheStore, rules: CacheRuleSet) -> None:
        self._cache = cache
        self._rules = rules

    async def get_or_invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        invoker: Callable[[], Awaitable[T]],
    ) -> T:
        operation = CacheOperationType.MCP_TOOL
        rule = self._rules.for_operation(operation)
        params = {"tool_name": tool_name, "arguments": arguments}
        if rule is not None and rule.enabled:
            key = build_cache_key(operation, params, prefix=rule.key_prefix)
            return await run_cache_aside(
                cache=self._cache,
                key=key,
                rule=rule,
                operation=operation.value,
                span=PortCallSpan(f"mcp_tool:{tool_name}"),
                serialize=McpToolCacheEnvelope.pack,
                deserialize=McpToolCacheEnvelope.unpack,
                loader=invoker,
            )

        return await invoker()
