"""Slim composition root for Vercel MCP (no LangGraph, RAG, or LLM wiring)."""

from __future__ import annotations

import logging

from mcp_server.application.mcp_tool_cache_runtime import set_mcp_tool_cache
from mcp_server.application.workflow_config import set_workflow_execution_config
from mcp_server.application.workflow_runtime import configure_lazy_document_video_workflow
from mcp_server.operational_config import load_operational_config
from mcp_server.settings import load_settings
from mcp_server.wiring import (
    build_mcp_tool_cache,
    build_workflow_execution_config,
    create_cache_store,
)

logger = logging.getLogger(__name__)


def initialize_vercel_runtime() -> None:
    """Wire only MCP document/video tools — Supabase + YouTube, no local RAG stack."""
    operational = load_operational_config()
    set_workflow_execution_config(build_workflow_execution_config(operational))

    try:
        settings = load_settings()
    except Exception as exc:
        logger.warning("Vercel MCP settings not loaded; tools will return errors until env is set: %s", exc)
        set_mcp_tool_cache(None)
        configure_lazy_document_video_workflow(None)
        return

    cache_store = create_cache_store(settings)
    configure_lazy_document_video_workflow(settings, cache_store)
    set_mcp_tool_cache(build_mcp_tool_cache(settings, cache_store))
