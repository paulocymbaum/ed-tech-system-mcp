"""Pure MCP transport kwargs for hosted and local deployments."""

from __future__ import annotations

from typing import Any, Literal

McpTransport = Literal["stdio", "http", "sse", "streamable-http"]


def parse_allowed_hosts(raw: str) -> list[str]:
    """Split a comma-separated host allowlist."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_mcp_run_kwargs(
    *,
    transport: McpTransport,
    host: str,
    port: int,
    stateless_http: bool = False,
    host_origin_protection: bool | Literal["auto"] | None = None,
    allowed_hosts: str = "",
) -> dict[str, Any]:
    """Map transport settings to FastMCP ``run()`` keyword arguments."""
    if transport == "stdio":
        return {"transport": "stdio"}

    kwargs: dict[str, Any] = {
        "transport": transport,
        "host": host,
        "port": port,
    }
    if stateless_http:
        kwargs["stateless_http"] = True
    if host_origin_protection is not None:
        kwargs["host_origin_protection"] = host_origin_protection
    parsed_hosts = parse_allowed_hosts(allowed_hosts)
    if parsed_hosts:
        kwargs["allowed_hosts"] = parsed_hosts
    return kwargs
