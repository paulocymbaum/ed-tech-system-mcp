"""FastAPI app for local LangGraph workflow visualization."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from mcp_server.application.agent import (
    list_registered_workflows,
    workflow_timeout_seconds,
)
from mcp_server.application.agents.content_generation.graph import (
    get_content_generation_graph,
    initial_content_generation_state,
)
from mcp_server.application.agents.rag_retrieval.graph import (
    get_rag_retrieval_graph,
    initial_rag_retrieval_state,
)
from mcp_server.application.agents.rag_validation.graph import (
    get_rag_validation_graph,
    initial_rag_validation_state,
    rag_validation_workflow_timeout_seconds,
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
from mcp_server.application.benchmark_runner import (
    BenchmarkCompleteEvent,
    BenchmarkErrorEvent,
    BenchmarkProgressEvent,
    BenchmarkStreamEvent,
    RagOptimizationCompleteEvent,
    RagOptimizationErrorEvent,
    RagOptimizationProgressEvent,
    RagOptimizationStreamEvent,
    list_benchmarks,
    stream_benchmark,
    stream_rag_optimization,
)
from mcp_server.application.workflow_graph import WorkflowGraphView, workflow_graph_view
from mcp_server.application.workflow_trace import invoke_graph_with_trace
from mcp_server.domain.exceptions import ResourceNotFoundError
from mcp_server.domain.rag_hyperparameters import RagHyperparameters
from mcp_server.interface.local_ui.benchmark_schemas import (
    BenchmarkCompleteEventView,
    BenchmarkErrorEventView,
    BenchmarkProgressEventView,
    BenchmarkSummaryView,
    RagBenchmarkRunRequest,
    RagOptimizationCompleteEventView,
    RagOptimizationErrorEventView,
    RagOptimizationProgressEventView,
    RagOptimizationReportView,
    RagOptimizationRequest,
    TestDatasetSummaryView,
)
from mcp_server.interface.local_ui.schemas import WorkflowListResponse
from mcp_server.interface.validation import (
    ContentGenerationRunRequest,
    ContentGenerationRunResponse,
    RagRetrievalRunRequest,
    RagRetrievalRunResponse,
    RagValidationDocumentDefaults,
    RagValidationRunRequest,
    RagValidationRunResponse,
    ResearchArticleRunRequest,
    ResearchArticleRunResponse,
    TavilySearchRunRequest,
    TavilySearchRunResponse,
    YouTubeSearchRunRequest,
    YouTubeSearchRunResponse,
    content_generation_state_to_run_response,
    rag_retrieval_state_to_run_response,
    rag_validation_state_to_run_response,
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


async def _run_tavily_workflow(body: dict[str, object]) -> TavilySearchRunResponse:
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


async def _run_youtube_workflow(body: dict[str, object]) -> YouTubeSearchRunResponse:
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


async def _run_research_article_workflow(body: dict[str, object]) -> ResearchArticleRunResponse:
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


async def _run_content_generation_workflow(
    body: dict[str, object],
) -> ContentGenerationRunResponse:
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


async def _run_rag_retrieval_workflow(body: dict[str, object]) -> RagRetrievalRunResponse:
    request = RagRetrievalRunRequest.model_validate(body)
    try:
        graph = get_rag_retrieval_graph()
        state = initial_rag_retrieval_state(
            request.query,
            retrieval_mode=request.retrieval_mode,
            retrieve_limit=request.retrieve_limit,
            rerank_top_n=request.rerank_top_n,
            rerank_enabled=request.rerank_enabled,
            course_id=request.course_id,
            tags=request.tags,
            language=request.language,
        )
        result, trace = await invoke_graph_with_trace(
            graph,
            state,
            timeout_seconds=workflow_timeout_seconds(),
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Workflow execution timed out.",
        ) from exc
    return rag_retrieval_state_to_run_response(result, trace=trace)


async def _run_rag_validation_workflow(body: dict[str, object]) -> RagValidationRunResponse:
    request = RagValidationRunRequest.model_validate(body)
    try:
        graph = get_rag_validation_graph()
        state = initial_rag_validation_state(
            request.query,
            fixture_path=request.fixture_path,
            document_text=request.document_text,
            document_title=request.document_title,
            expected_phrases=request.expected_phrases,
            retrieval_mode=request.retrieval_mode,
            retrieve_limit=request.retrieve_limit,
            rerank_top_n=request.rerank_top_n,
            rerank_enabled=request.rerank_enabled,
            course_id=request.course_id,
            tags=request.tags,
            language=request.language,
        )
        result, trace = await invoke_graph_with_trace(
            graph,
            state,
            timeout_seconds=rag_validation_workflow_timeout_seconds(),
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Workflow execution timed out.",
        ) from exc
    return rag_validation_state_to_run_response(result, trace=trace)


def _optimization_event_to_view(event: RagOptimizationStreamEvent) -> dict[str, object]:
    if isinstance(event, RagOptimizationProgressEvent):
        return RagOptimizationProgressEventView(
            stage=event.stage,
            progress=event.progress,
            message=event.message,
            scenario_count=event.scenario_count,
            combination_index=event.combination_index,
            combination_total=event.combination_total,
        ).model_dump()
    if isinstance(event, RagOptimizationCompleteEvent):
        return RagOptimizationCompleteEventView(
            stage="complete",
            progress=event.progress,
            message=event.message,
            report=event.report,
            optimized_hyperparameters=event.optimized_hyperparameters,
        ).model_dump()
    if isinstance(event, RagOptimizationErrorEvent):
        return RagOptimizationErrorEventView(
            stage="error",
            progress=event.progress,
            message=event.message,
        ).model_dump()
    msg = f"Unsupported optimization event type: {type(event)!r}"
    raise TypeError(msg)


async def _rag_optimization_sse_stream(request: RagOptimizationRequest) -> AsyncIterator[str]:
    baseline = RagHyperparameters(
        retrieval_mode=request.retrieval_mode,
        retrieve_limit=request.retrieve_limit,
        rerank_enabled=request.rerank_enabled,
        rerank_top_n=request.rerank_top_n,
    )
    try:
        async for event in stream_rag_optimization(
            max_scenarios=request.max_scenarios,
            max_combinations=request.max_combinations,
            baseline=baseline,
        ):
            payload = _optimization_event_to_view(event)
            yield f"data: {json.dumps(payload)}\n\n"
            if isinstance(event, (RagOptimizationCompleteEvent, RagOptimizationErrorEvent)):
                return
    except ValueError as exc:
        error = RagOptimizationErrorEventView(
            stage="error",
            progress=0,
            message=str(exc),
        )
        yield f"data: {json.dumps(error.model_dump())}\n\n"


def _benchmark_event_to_view(event: BenchmarkStreamEvent) -> dict[str, object]:
    if isinstance(event, BenchmarkProgressEvent):
        return BenchmarkProgressEventView(
            stage=event.stage,
            progress=event.progress,
            message=event.message,
            step=event.step,
            total=event.total,
            node_id=event.node_id,
            scenario_id=event.scenario_id,
            scenario_index=event.scenario_index,
            scenario_total=event.scenario_total,
        ).model_dump()
    if isinstance(event, BenchmarkCompleteEvent):
        result = rag_validation_state_to_run_response(event.state, trace=event.trace)
        return BenchmarkCompleteEventView(
            stage="complete",
            progress=event.progress,
            message=event.message,
            result=result,
            dataset_report=event.dataset_report,
        ).model_dump()
    if isinstance(event, BenchmarkErrorEvent):
        return BenchmarkErrorEventView(
            stage="error",
            progress=event.progress,
            message=event.message,
        ).model_dump()
    msg = f"Unsupported benchmark event type: {type(event)!r}"
    raise TypeError(msg)


async def _benchmark_sse_stream(
    benchmark_id: str,
    body: dict[str, object],
) -> AsyncIterator[str]:
    try:
        if benchmark_id == "rag":
            rag_request = RagBenchmarkRunRequest.model_validate(body)
            event_stream = stream_benchmark(
                benchmark_id,
                hyperparameters=RagHyperparameters(
                    retrieval_mode=rag_request.retrieval_mode,
                    retrieve_limit=rag_request.retrieve_limit,
                    rerank_enabled=rag_request.rerank_enabled,
                    rerank_top_n=rag_request.rerank_top_n,
                ),
                max_scenarios=rag_request.max_scenarios,
            )
        else:
            validation_request = RagValidationRunRequest.model_validate(body)
            event_stream = stream_benchmark(
                benchmark_id,
                query=validation_request.query,
                fixture_path=validation_request.fixture_path,
                document_text=validation_request.document_text,
                document_title=validation_request.document_title,
                expected_phrases=validation_request.expected_phrases,
                retrieval_mode=validation_request.retrieval_mode,
                retrieve_limit=validation_request.retrieve_limit,
                rerank_top_n=validation_request.rerank_top_n,
                rerank_enabled=validation_request.rerank_enabled,
                course_id=validation_request.course_id,
                tags=validation_request.tags,
                language=validation_request.language,
            )
        async for event in event_stream:
            payload = _benchmark_event_to_view(event)
            yield f"data: {json.dumps(payload)}\n\n"
    except ResourceNotFoundError as exc:
        error = BenchmarkErrorEventView(
            stage="error",
            progress=0,
            message=str(exc),
        )
        yield f"data: {json.dumps(error.model_dump())}\n\n"
    except ValueError as exc:
        error = BenchmarkErrorEventView(
            stage="error",
            progress=0,
            message=str(exc),
        )
        yield f"data: {json.dumps(error.model_dump())}\n\n"
    except FileNotFoundError as exc:
        error = BenchmarkErrorEventView(
            stage="error",
            progress=0,
            message=str(exc),
        )
        yield f"data: {json.dumps(error.model_dump())}\n\n"


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

    @app.get("/api/benchmarks", response_model=list[BenchmarkSummaryView])
    def list_benchmark_catalog() -> list[BenchmarkSummaryView]:
        return [
            BenchmarkSummaryView(
                id=item.id,
                name=item.name,
                description=item.description,
                workflow_id=item.workflow_id,
            )
            for item in list_benchmarks()
        ]

    @app.get("/api/workflows/{workflow_id}", response_model=WorkflowGraphView)
    def get_workflow(workflow_id: str) -> WorkflowGraphView:
        workflow = _workflow_index().get(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")
        return workflow

    @app.get(
        "/api/workflows/rag-validation/document-defaults",
        response_model=RagValidationDocumentDefaults,
    )
    def get_rag_validation_document_defaults() -> RagValidationDocumentDefaults:
        from mcp_server.application.agents.rag_validation.fixture import default_document_defaults

        payload = default_document_defaults()
        return RagValidationDocumentDefaults.model_validate(payload)

    @app.post("/api/workflows/{workflow_id}/run")
    async def run_workflow(
        workflow_id: str,
        body: dict[str, object],
    ) -> (
        TavilySearchRunResponse
        | YouTubeSearchRunResponse
        | ResearchArticleRunResponse
        | ContentGenerationRunResponse
        | RagRetrievalRunResponse
        | RagValidationRunResponse
    ):
        if workflow_id == "tavily-search":
            return await _run_tavily_workflow(body)
        if workflow_id == "youtube-search":
            return await _run_youtube_workflow(body)
        if workflow_id == "research-article":
            return await _run_research_article_workflow(body)
        if workflow_id == "content-generation":
            return await _run_content_generation_workflow(body)
        if workflow_id == "rag-retrieval":
            return await _run_rag_retrieval_workflow(body)
        if workflow_id == "rag-validation":
            return await _run_rag_validation_workflow(body)
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

    @app.post("/api/benchmarks/{benchmark_id}/run")
    async def run_benchmark(benchmark_id: str, body: dict[str, object]) -> StreamingResponse:
        from mcp_server.application.benchmark_runner import get_benchmark

        if get_benchmark(benchmark_id) is None:
            raise HTTPException(status_code=404, detail=f"Benchmark '{benchmark_id}' not found.")
        return StreamingResponse(
            _benchmark_sse_stream(benchmark_id, body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/benchmarks/rag/optimize")
    async def optimize_rag_hyperparameters(
        body: RagOptimizationRequest | None = None,
    ) -> StreamingResponse:
        request = body or RagOptimizationRequest()
        return StreamingResponse(
            _rag_optimization_sse_stream(request),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get(
        "/api/benchmarks/rag/optimization-report",
        response_model=RagOptimizationReportView,
    )
    def get_rag_optimization_report() -> RagOptimizationReportView:
        from mcp_server.application.agents.rag_validation.optimization_report import (
            load_optimization_report,
        )

        report = load_optimization_report()
        if report is None:
            raise HTTPException(status_code=404, detail="Optimization report not found.")
        return RagOptimizationReportView.model_validate(report.as_dict())

    @app.get(
        "/api/benchmarks/rag/test-dataset-summary",
        response_model=TestDatasetSummaryView,
    )
    def get_rag_test_dataset_summary() -> TestDatasetSummaryView:
        from mcp_server.application.agents.rag_validation.test_dataset_loader import (
            TestDatasetNotFoundError,
            summarize_test_dataset,
        )

        try:
            summary = summarize_test_dataset()
        except TestDatasetNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return TestDatasetSummaryView.model_validate(summary.as_dict())

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
