"""Runtime accessor for MCP tool interaction caching."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class McpToolCachePort(Protocol):
    """Application port for cache-aside MCP tool invocation."""

    async def get_or_invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        invoker: Callable[[], Awaitable[T]],
    ) -> T:
        """Return a cached tool result or invoke the handler on miss."""


_runtime_mcp_tool_cache: McpToolCachePort | None = None


def set_mcp_tool_cache(cache: McpToolCachePort | None) -> None:
    """Store the wired MCP tool cache helper for interface consumers."""
    global _runtime_mcp_tool_cache
    _runtime_mcp_tool_cache = cache


def get_mcp_tool_cache() -> McpToolCachePort | None:
    """Return the MCP tool cache initialized at startup, if any."""
    return _runtime_mcp_tool_cache


def reset_mcp_tool_cache() -> None:
    """Clear the runtime MCP tool cache (for tests)."""
    set_mcp_tool_cache(None)
