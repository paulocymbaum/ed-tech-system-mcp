"""MCP tool for LangGraph workflow execution (Docker / Render / local — requires full stack)."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from mcp_server.application.agent import run_document_video_graph
from mcp_server.application.mcp_tool_cache_runtime import get_mcp_tool_cache
from mcp_server.domain.exceptions import DomainError
from mcp_server.interface.custom_tools import _cached_tool_invoke
from mcp_server.interface.error_mapping import raise_as_mcp_error
from mcp_server.interface.mcp_server import mcp
from mcp_server.interface.validation_workflow import (
    WorkflowRunRequest,
    WorkflowRunResponse,
    workflow_state_to_run_response,
)

logger = logging.getLogger(__name__)


async def _invoke_run_workflow(request: WorkflowRunRequest) -> WorkflowRunResponse:
    result = await run_document_video_graph(
        request.query,
        document_limit=request.document_limit,
        video_limit=request.video_limit,
    )
    return workflow_state_to_run_response(result)


@mcp.tool
async def run_workflow(
    query: str,
    document_limit: int = 10,
    video_limit: int = 5,
) -> WorkflowRunResponse:
    """Execute the document + video discovery LangGraph workflow."""
    request = WorkflowRunRequest(
        query=query,
        document_limit=document_limit,
        video_limit=video_limit,
    )
    args = request.model_dump()
    return await _cached_tool_invoke(
        "run_workflow",
        args,
        lambda: _invoke_run_workflow(request),
    )
