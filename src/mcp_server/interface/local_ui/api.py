"""FastAPI app for local LangGraph workflow visualization."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from mcp_server.application.agent import (
    list_registered_workflows,
    workflow_timeout_seconds,
)
from mcp_server.application.agents.content_generation.graph import (
    get_content_generation_graph,
    initial_content_generation_state,
)
from mcp_server.application.agents.research_article.graph import (
    get_research_article_graph,
    initial_research_article_state,
)
from mcp_server.application.agents.tavily_search.graph import (
    get_tavily_search_graph,
    initial_tavily_search_state,
)
from mcp_server.application.agents.youtube_search.graph import (
    get_youtube_search_graph,
    initial_youtube_search_state,
)
from mcp_server.application.workflow_graph import WorkflowGraphView, workflow_graph_view
from mcp_server.application.workflow_trace import invoke_graph_with_trace
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.interface.local_ui.schemas import WorkflowListResponse
from mcp_server.interface.validation import (
    ContentGenerationRunRequest,
    ContentGenerationRunResponse,
    ResearchArticleRunRequest,
    ResearchArticleRunResponse,
    TavilySearchRunRequest,
    TavilySearchRunResponse,
    YouTubeSearchRunRequest,
    YouTubeSearchRunResponse,
    content_generation_state_to_run_response,
    research_article_state_to_run_response,
    tavily_search_state_to_run_response,
    youtube_search_state_to_run_response,
)
from mcp_server.main import bootstrap_application_runtime, bootstrap_environment

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_LOCAL_ORIGINS = {
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://127.0.0.1:8877",
    "http://localhost:8877",
}


def assert_local_development() -> None:
    """Refuse to start the workflow UI outside local development."""
    app_env = os.getenv("APP_ENV", "development")
    if app_env not in {"development", "local"}:
        msg = "Workflow UI is only available when APP_ENV is development or local."
        raise RuntimeError(msg)


def _workflow_index() -> dict[str, WorkflowGraphView]:
    return {workflow.id: workflow_graph_view(workflow) for workflow in list_registered_workflows()}


@asynccontextmanager
async def _local_ui_lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Wire the composition root when settings are available (optional for graph browsing)."""
    bootstrap_environment()
    try:
        bootstrap_application_runtime()
    except Exception as exc:
        logging.getLogger(__name__).warning(
            "Workflow UI graph browsing is available, but workflow execution is not wired: %s",
            exc,
        )
    yield


def create_local_ui_app(*, bootstrap_runtime: bool = False) -> FastAPI:
    """Create the local-only FastAPI application."""
    assert_local_development()

    lifespan = _local_ui_lifespan if bootstrap_runtime else None

    app = FastAPI(
        title="Ed-Tech Workflow UI",
        description="Local development UI for LangChain and LangGraph workflows.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(_LOCAL_ORIGINS),
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str | int]:
        return {
            "status": "ok",
            "mode": "local",
            "workflow_count": len(list_registered_workflows()),
        }

    @app.get("/api/workflows", response_model=WorkflowListResponse)
    def list_workflows() -> WorkflowListResponse:
        return list(_workflow_index().values())

    @app.get("/api/workflows/{workflow_id}", response_model=WorkflowGraphView)
    def get_workflow(workflow_id: str) -> WorkflowGraphView:
        workflow = _workflow_index().get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
        return workflow

    @app.post("/api/workflows/{workflow_id}/run")
    async def run_workflow(
        workflow_id: str,
        body: dict[str, object],
    ) -> (
        TavilySearchRunResponse
        | YouTubeSearchRunResponse
        | ResearchArticleRunResponse
        | ContentGenerationRunResponse
    ):
        if workflow_id == "tavily-search":
            request = TavilySearchRunRequest.model_validate(body)
            try:
                graph = get_tavily_search_graph()
                state = initial_tavily_search_state(
                    request.query,
                    max_results=request.max_results,
                )
                result, trace = await invoke_graph_with_trace(
                    graph,
                    state,
                    timeout_seconds=workflow_timeout_seconds(),
                )
            except ResourceNotFoundError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except TimeoutError as exc:
                raise HTTPException(
                    status_code=504,
                    detail="Workflow execution timed out.",
                ) from exc
            return tavily_search_state_to_run_response(result, trace=trace)

        if workflow_id == "youtube-search":
            request = YouTubeSearchRunRequest.model_validate(body)
            try:
                graph = get_youtube_search_graph()
                state = initial_youtube_search_state(
                    request.query,
                    max_results=request.max_results,
                    language=request.language,
                    safe_search=request.safe_search,
                )
                result, trace = await invoke_graph_with_trace(
                    graph,
                    state,
                    timeout_seconds=workflow_timeout_seconds(),
                )
            except ResourceNotFoundError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except TimeoutError as exc:
                raise HTTPException(
                    status_code=504,
                    detail="Workflow execution timed out.",
                ) from exc
            return youtube_search_state_to_run_response(result, trace=trace)

        if workflow_id == "research-article":
            request = ResearchArticleRunRequest.model_validate(body)
            try:
                graph = get_research_article_graph()
                state = initial_research_article_state(
                    request.query,
                    max_web_results=request.max_web_results,
                    max_video_results=request.max_video_results,
                )
                result, trace = await invoke_graph_with_trace(
                    graph,
                    state,
                    timeout_seconds=workflow_timeout_seconds(),
                )
            except ResourceNotFoundError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except TimeoutError as exc:
                raise HTTPException(
                    status_code=504,
                    detail="Workflow execution timed out.",
                ) from exc
            return research_article_state_to_run_response(result, trace=trace)

        if workflow_id == "content-generation":
            request = ContentGenerationRunRequest.model_validate(body)
            try:
                graph = get_content_generation_graph()
                state = initial_content_generation_state(
                    request.topic,
                    grade_level=request.grade_level,
                )
                result, trace = await invoke_graph_with_trace(
                    graph,
                    state,
                    timeout_seconds=workflow_timeout_seconds(),
                )
            except ResourceNotFoundError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            except TimeoutError as exc:
                raise HTTPException(
                    status_code=504,
                    detail="Workflow execution timed out.",
                ) from exc
            return content_generation_state_to_run_response(result, trace=trace)

        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

    static_dir = Path(__file__).resolve().parents[4] / "ui" / "dist"
    if static_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/")
        def serve_ui() -> FileResponse:
            return FileResponse(static_dir / "index.html")

    return app


app = create_local_ui_app(bootstrap_runtime=True)


def local_ui_host() -> str:
    """Bind address for the local workflow UI."""
    host = os.getenv("LOCAL_UI_HOST", "127.0.0.1")
    if host not in _LOCAL_HOSTS:
        msg = f"LOCAL_UI_HOST must be a loopback address, got '{host}'."
        raise RuntimeError(msg)
    return host


def local_ui_port() -> int:
    """TCP port for the local workflow UI."""
    return int(os.getenv("LOCAL_UI_PORT", "8877"))
