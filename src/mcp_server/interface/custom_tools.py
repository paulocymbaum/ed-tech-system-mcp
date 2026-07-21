"""MCP tool wrappers around application workflows.

Tool implementations deferred — register tools here once workflows are ready.
"""

from mcp_server.interface.mcp_server import mcp


@mcp.tool
def health_check() -> str:
    """Verify the MCP server is running."""
    return "ok"
