"""Sequential document + video discovery without LangGraph (MCP / lightweight paths)."""

from __future__ import annotations

import asyncio

from mcp_server.application.document_video_state import DocumentVideoState
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
)
from mcp_server.application.workflow_runtime import get_document_video_workflow
from mcp_server.domain.exceptions import ResourceNotFoundError


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def workflow_timeout_seconds() -> float:
    return _workflow_runtime_config().workflow_timeout_seconds


def _require_workflow():
    workflow = get_document_video_workflow()
    if workflow is None:
        raise ResourceNotFoundError("Document video workflow has not been initialized")
    return workflow


def initial_document_video_state(
    query: str,
    *,
    document_limit: int = 10,
    video_limit: int = 5,
) -> DocumentVideoState:
    return DocumentVideoState(
        query=query,
        document_limit=document_limit,
        video_limit=video_limit,
        search_terms=query,
        document_count=0,
        video_count=0,
    )


async def run_document_video_workflow(
    query: str,
    *,
    document_limit: int = 10,
    video_limit: int = 5,
    timeout_seconds: float | None = None,
) -> DocumentVideoState:
    """Run fetch → derive → search sequentially with workflow timeout enforcement."""

    async def _run() -> DocumentVideoState:
        workflow = _require_workflow()
        documents = await workflow.fetch_documents(query, document_limit)
        search_terms = workflow.derive_search_terms(query, documents)
        videos = await workflow.search_videos(search_terms, video_limit)
        return DocumentVideoState(
            query=query,
            document_limit=document_limit,
            video_limit=video_limit,
            search_terms=search_terms,
            document_count=len(documents),
            video_count=len(videos),
            documents=documents,
            videos=videos,
        )

    return await asyncio.wait_for(
        _run(),
        timeout=timeout_seconds if timeout_seconds is not None else workflow_timeout_seconds(),
    )
