"""Vercel serverless entrypoint for the MCP streamable HTTP transport."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

os.environ.setdefault("APP_ENV", "production")

from mcp_server.interface.custom_tools import (  # noqa: F401
    find_documents,
    health_check,
    run_workflow,
    search_youtube,
)
from mcp_server.interface.mcp_server import create_mcp_server
from mcp_server.main import bootstrap_application_runtime, bootstrap_environment


def _bootstrap_or_warn() -> None:
    """Wire runtime on cold start; graph browsing may work even if secrets are missing."""
    bootstrap_environment()
    try:
        bootstrap_application_runtime()
    except Exception as exc:
        logger.warning("MCP runtime partially initialized on Vercel: %s", exc)


_bootstrap_or_warn()

_mcp_server = create_mcp_server()
app = _mcp_server.http_app(
    transport="streamable-http",
    stateless_http=True,
    host_origin_protection=False,
)
