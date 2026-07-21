"""MCP Server instantiation and tool routing."""

from fastmcp import FastMCP

mcp = FastMCP("ed-tech-system")


def create_mcp_server() -> FastMCP:
    """Return the configured MCP server instance."""
    return mcp
