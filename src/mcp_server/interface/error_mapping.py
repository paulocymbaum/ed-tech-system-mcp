"""Map domain exceptions to MCP protocol errors at the interface boundary."""

from __future__ import annotations

from typing import NoReturn

from fastmcp.exceptions import NotFoundError as FastMcpNotFoundError
from fastmcp.exceptions import ToolError
from mcp import McpError
from mcp.types import ErrorData

from mcp_server.domain.exceptions import (
    DomainAuthorizationError,
    DomainError,
    DomainValidationError,
    ExternalRateLimitError,
    ResourceNotFoundError,
)


def raise_as_mcp_error(error: DomainError) -> NoReturn:
    """Raise an MCP-protocol exception corresponding to a domain error."""
    if isinstance(error, ResourceNotFoundError):
        raise FastMcpNotFoundError(str(error)) from error
    if isinstance(error, DomainValidationError):
        raise McpError(ErrorData(code=-32602, message=f"Invalid params: {error}")) from error
    if isinstance(error, ExternalRateLimitError):
        raise ToolError(str(error)) from error
    if isinstance(error, DomainAuthorizationError):
        raise ToolError("Unauthorized") from error
    raise ToolError(str(error)) from error
