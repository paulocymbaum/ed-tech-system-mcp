"""MCP Server instantiation and tool routing."""

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_server.interface.privileged_tool_auth import PrivilegedToolAuthMiddleware

mcp = FastMCP("ed-tech-system")
mcp.add_middleware(PrivilegedToolAuthMiddleware())


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def http_health(_request: Request) -> JSONResponse:
    """Liveness probe for container orchestrators and load balancers."""
    return JSONResponse({"status": "ok", "service": "ed-tech-system-mcp"})


def create_mcp_server() -> FastMCP:
    """Return the configured MCP server instance."""
    return mcp
