"""Tests for the local workflow UI API."""

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from mcp_server.application.integration_runtime import reset_integration_clients
from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.application.retrieval_runtime import (
    reset_retrieval_clients,
    set_chunking_strategy,
    set_embedding_provider,
    set_reranker,
    set_vector_index_writer,
    set_vector_retriever,
)
from mcp_server.application.token_counting_runtime import set_token_counter
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.infrastructure.rerank.noop_reranker import NoOpReranker
from mcp_server.infrastructure.token_counting.tiktoken_counter import TiktokenTokenCounter
from mcp_server.interface.local_ui.api import create_local_ui_app
from mcp_server.main import bootstrap_application_runtime, bootstrap_environment
from mcp_server.operational_config import load_operational_config
from mcp_server.settings import load_settings
from rag_fakes import (
    FakeChunkingStrategy,
    FakeEmbeddingProvider,
    FixtureAwareRetriever,
    RecordingIndexWriter,
)


class _UiContentModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "ui-content-stub"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = "\n".join(str(message.content) for message in messages).lower()
        if "quiz" in text and "assessment" in text:
            payload = {
                "title": "Quiz: fractions",
                "questions": [
                    {
                        "question": "Q1",
                        "options": ["A", "B"],
                        "correct_answer": "A",
                        "explanation": "Because A.",
                    },
                    {
                        "question": "Q2",
                        "options": ["A", "B"],
                        "correct_answer": "A",
                        "explanation": "Because A.",
                    },
                    {
                        "question": "Q3",
                        "options": ["A", "B"],
                        "correct_answer": "A",
                        "explanation": "Because A.",
                    },
                ],
            }
        elif "problem-based learning" in text:
            payload = {
                "title": "PBL: fractions",
                "driving_question": "How can we apply fractions?",
                "scenario": "A community project needs help dividing resources fairly.",
                "learning_objectives": ["Apply fractions"],
                "deliverables": [
                    {"name": "Plan", "description": "A written project plan with milestones."}
                ],
                "duration_days": 5,
            }
        else:
            payload = {
                "title": "Lesson: fractions",
                "topic": "fractions",
                "grade_level": "6th grade",
                "objectives": ["Understand fractions"],
                "sections": [
                    {"heading": "Intro", "content": "Fractions represent parts of a whole."},
                    {"heading": "Practice", "content": "Students solve guided fraction problems."},
                ],
                "summary": "Students understand fractions as parts of a whole.",
            }
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=json.dumps(payload)))]
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def _bootstrap_live_runtime() -> None:
    bootstrap_environment()
    bootstrap_application_runtime(load_operational_config(), load_settings())


def test_list_workflows_returns_langgraph_metadata() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows")

    assert response.status_code == 200
    workflows = response.json()
    assert len(workflows) >= 2
    workflow = workflows[0]
    assert workflow["framework"] == "langgraph"
    assert any(node["kind"] == "start" for node in workflow["nodes"])
    assert any(edge["source"] == "__start__" for edge in workflow["edges"])
    workflow_ids = {item["id"] for item in workflows}
    assert "tavily-search" in workflow_ids
    assert "youtube-search" in workflow_ids


def test_get_unknown_workflow_returns_404() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows/does-not-exist")

    assert response.status_code == 404


def test_post_run_content_generation_returns_response_when_wired() -> None:
    set_chat_model(_UiContentModel())
    set_token_counter(TiktokenTokenCounter())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/content-generation/run",
        json={"topic": "fractions", "grade_level": "6th grade"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["topic"] == "fractions"
    assert body["generation_complete"] is True
    assert body["lesson"]["topic"] == "fractions"
    assert len(body["quiz"]["questions"]) >= 3
    llm_steps = [step for step in body["trace"] if step.get("llm_io")]
    assert llm_steps
    assert llm_steps[0]["llm_io"]["input_tokens"] > 0
    assert llm_steps[0]["llm_io"]["total_tokens"] > 0
    reset_chat_model()


@pytest.mark.skipif(
    not os.getenv("TAVILY_API_KEY"),
    reason="TAVILY_API_KEY not set",
)
def test_post_run_tavily_search_returns_live_results() -> None:
    reset_integration_clients()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    _bootstrap_live_runtime()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/tavily-search/run",
        json={"query": "education", "max_results": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "education"
    assert body["result_count"] >= 1
    assert len(body["results"]) >= 1
    assert len(body["trace"]) >= 1
    assert body["trace"][0]["node_id"] == "search_web"
    reset_integration_clients()


@pytest.mark.skipif(
    not os.getenv("YOUTUBE_API_KEY"),
    reason="YOUTUBE_API_KEY not set",
)
def test_post_run_youtube_search_returns_live_results() -> None:
    reset_integration_clients()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    _bootstrap_live_runtime()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/youtube-search/run",
        json={"query": "education", "max_results": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "education"
    assert body["video_count"] >= 1
    assert len(body["videos"]) >= 1
    assert body["videos"][0]["url"].startswith("https://www.youtube.com/watch?v=")
    assert len(body["trace"]) >= 1
    assert body["trace"][0]["node_id"] == "search_videos"
    reset_integration_clients()


def test_post_run_tavily_search_returns_503_when_uninitialized() -> None:
    reset_integration_clients()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/tavily-search/run",
        json={"query": "algebra"},
    )

    assert response.status_code == 503
    assert "not been initialized" in response.json()["detail"]


def test_post_run_youtube_search_returns_503_when_uninitialized() -> None:
    reset_integration_clients()
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/youtube-search/run",
        json={"query": "algebra"},
    )

    assert response.status_code == 503
    assert "not been initialized" in response.json()["detail"]


def test_post_run_rag_validation_returns_response_when_wired() -> None:
    set_token_counter(TiktokenTokenCounter())
    writer = RecordingIndexWriter()
    set_chunking_strategy(FakeChunkingStrategy())
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(FixtureAwareRetriever(writer))
    set_reranker(NoOpReranker())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/workflows/rag-validation/run",
        json={
            "query": "How does photosynthesis convert light energy?",
            "document_title": "Custom corpus",
            "document_text": (
                "# Custom\n\n"
                "Photosynthesis uses chlorophyll during light-dependent reactions "
                "to make glucose."
            ),
            "expected_phrases": ["chlorophyll", "light-dependent reactions", "glucose"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["index_complete"] is True
    assert body["validation_passed"] is True
    assert body["document_title"] == "Custom corpus"
    assert body["document_source"] == "inline"
    assert body["chunk_count"] >= 1
    assert body["rag_benchmarks"]["phrase_coverage"] == 1.0
    assert body["rag_benchmarks"]["any_phrase_hit"] == 1.0
    assert body["rag_evaluation_context"]["score_kind"] in {"cosine", "rrf", "reranker"}
    assert body["matched_phrases"] == ["chlorophyll", "light-dependent reactions", "glucose"]
    assert body["missing_phrases"] == []
    assert len(body["trace"]) >= 6
    validate_steps = [step for step in body["trace"] if step["node_id"] == "validate_retrieval"]
    assert validate_steps
    assert validate_steps[0]["output_update"]["rag_benchmarks"]["phrase_coverage"] == 1.0
    assert "rag_evaluation_context" in validate_steps[0]["output_update"]
    merge_steps = [step for step in body["trace"] if step["node_id"] == "merge_context"]
    assert merge_steps
    assert "retrieval_metrics" in merge_steps[0]["output_update"]
    assert "rag_evaluation_context" in merge_steps[0]["output_update"]
    node_ids = {step["node_id"] for step in body["trace"]}
    assert "load_document" in node_ids
    assert "index_document" in node_ids
    assert "embed_query" in node_ids
    assert "validate_retrieval" in node_ids
    reset_retrieval_clients()
    reset_workflow_execution_config()


def test_list_workflows_includes_rag_validation_node_groups() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows/rag-validation")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "rag-validation"
    group_ids = {group["id"] for group in body["node_groups"]}
    assert "rag_pipeline" in group_ids
    assert "document_pipeline" in group_ids


def test_get_rag_validation_document_defaults() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/workflows/rag-validation/document-defaults")

    assert response.status_code == 200
    body = response.json()
    assert "chlorophyll" in body["document_text"]
    assert body["expected_phrases"]


def test_get_rag_validation_document_defaults_includes_suggested_hyperparameters_when_optimized_file_exists(
    tmp_path: Path,
) -> None:
    from mcp_server.application.agents.rag_validation.fixture import (
        save_optimized_hyperparameters,
    )
    from mcp_server.domain.rag_hyperparameters import (
        OBJECTIVE_MEAN_PHRASE_COVERAGE,
        OptimizedRagHyperparameters,
        RagHyperparameters,
    )

    hyperparameters = RagHyperparameters(
        retrieval_mode="vector",
        retrieve_limit=8,
        rerank_enabled=False,
        rerank_top_n=6,
    )
    result = OptimizedRagHyperparameters(
        optimized_at="2026-07-22T20:00:00+00:00",
        objective=OBJECTIVE_MEAN_PHRASE_COVERAGE,
        best_score=0.95,
        hyperparameters=hyperparameters,
        search_space={"retrieve_limits": [8]},
        results_summary=[{"mean_phrase_coverage": 0.95}],
    )
    optimized_path = save_optimized_hyperparameters(
        result,
        Path(tmp_path) / "optimized_hyperparameters.json",
    )

    with patch(
        "mcp_server.application.agents.rag_validation.fixture.OPTIMIZED_HYPERPARAMETERS_PATH",
        optimized_path,
    ):
        client = TestClient(create_local_ui_app())
        response = client.get("/api/workflows/rag-validation/document-defaults")

    assert response.status_code == 200
    body = response.json()
    assert body["suggested_hyperparameters"] == hyperparameters.as_dict()


def test_local_ui_lifespan_bootstraps_application_runtime() -> None:
    """Uvicorn reload workers import app directly; lifespan must wire the runtime."""
    with (
        patch("mcp_server.interface.local_ui.api.bootstrap_environment") as mock_env,
        patch("mcp_server.interface.local_ui.api.bootstrap_application_runtime") as mock_runtime,
        TestClient(create_local_ui_app(bootstrap_runtime=True)) as client,
    ):
        response = client.get("/api/health")

    assert response.status_code == 200
    mock_env.assert_called_once()
    mock_runtime.assert_called_once()


def test_list_benchmarks_returns_rag_entry() -> None:
    client = TestClient(create_local_ui_app())
    response = client.get("/api/benchmarks")

    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    rag = next(item for item in body if item["id"] == "rag")
    assert rag["workflow_id"] == "rag-validation"
    assert "RAG" in rag["name"]


def test_post_run_rag_benchmark_streams_progress_and_result() -> None:
    set_token_counter(TiktokenTokenCounter())
    writer = RecordingIndexWriter()
    set_chunking_strategy(FakeChunkingStrategy())
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(FixtureAwareRetriever(writer))
    set_reranker(NoOpReranker())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    client = TestClient(create_local_ui_app())

    with client.stream(
        "POST",
        "/api/benchmarks/rag/run",
        json={
            "max_scenarios": 1,
            "retrieval_mode": "vector",
            "retrieve_limit": 4,
            "rerank_enabled": False,
            "rerank_top_n": 4,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        events: list[dict[str, Any]] = []
        buffer = ""
        for chunk in response.iter_text():
            buffer += chunk
            while "\n\n" in buffer:
                block, buffer = buffer.split("\n\n", 1)
                for line in block.splitlines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

    progress_events = [event for event in events if event["stage"] not in {"complete", "error"}]
    assert progress_events
    assert {event["stage"] for event in progress_events} >= {"indexing", "validating"}
    assert any(event.get("scenario_id") for event in progress_events)
    assert all(0 <= event["progress"] <= 100 for event in progress_events)
    assert progress_events[0]["progress"] < progress_events[-1]["progress"]

    complete_events = [event for event in events if event["stage"] == "complete"]
    assert len(complete_events) == 1
    complete = complete_events[0]
    result = complete["result"]
    assert result["document_source"] == "test-dataset"
    assert "phrase_coverage" in result["rag_benchmarks"]
    assert complete["dataset_report"] is not None
    assert complete["dataset_report"]["scenario_count"] == 1
    assert complete["dataset_report"]["scenarios"]

    reset_retrieval_clients()
    reset_workflow_execution_config()


def test_post_run_unknown_benchmark_returns_404() -> None:
    client = TestClient(create_local_ui_app())
    response = client.post("/api/benchmarks/unknown/run", json={})

    assert response.status_code == 404


def test_post_run_rag_benchmark_sse_response_headers() -> None:
    set_token_counter(TiktokenTokenCounter())
    writer = RecordingIndexWriter()
    set_chunking_strategy(FakeChunkingStrategy())
    set_embedding_provider(FakeEmbeddingProvider())
    set_vector_index_writer(writer)
    set_vector_retriever(FixtureAwareRetriever(writer))
    set_reranker(NoOpReranker())
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=0,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )
    client = TestClient(create_local_ui_app())

    with client.stream(
        "POST",
        "/api/benchmarks/rag/run",
        json={"max_scenarios": 1, "retrieve_limit": 4, "rerank_enabled": False},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers.get("cache-control") == "no-cache"

    reset_retrieval_clients()
    reset_workflow_execution_config()


def test_post_run_rag_benchmark_streams_error_on_runner_failure() -> None:
    from mcp_server.application.benchmark_runner import BenchmarkErrorEvent

    async def _error_stream(*_args: object, **_kwargs: object):
        yield BenchmarkErrorEvent(
            stage="error",
            progress=0,
            message="Benchmark execution failed.",
        )

    client = TestClient(create_local_ui_app())

    with patch(
        "mcp_server.interface.local_ui.api.stream_benchmark",
        _error_stream,
    ):
        with client.stream(
            "POST",
            "/api/benchmarks/rag/run",
            json={},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")

            events: list[dict[str, Any]] = []
            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    for line in block.splitlines():
                        if line.startswith("data: "):
                            events.append(json.loads(line[6:]))

    error_events = [event for event in events if event["stage"] == "error"]
    assert len(error_events) == 1
    assert error_events[0]["progress"] == 0
    assert error_events[0]["message"] == "Benchmark execution failed."


def test_get_rag_test_dataset_summary_returns_counts() -> None:
    from mcp_server.application.agents.rag_validation.test_dataset_loader import TestDatasetSummary

    summary = TestDatasetSummary(
        total_scenarios=42,
        eval_scenarios=20,
        answer_in_corpus_scenarios=15,
        default_max_scenarios=12,
        scenario_ids=("SC0001", "SC0002"),
    )
    client = TestClient(create_local_ui_app())

    with patch(
        "mcp_server.application.agents.rag_validation.test_dataset_loader.summarize_test_dataset",
        return_value=summary,
    ):
        response = client.get("/api/benchmarks/rag/test-dataset-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_scenarios"] == 42
    assert body["answer_in_corpus_scenarios"] == 15
    assert body["scenario_ids"] == ["SC0001", "SC0002"]


def test_get_rag_test_dataset_summary_returns_503_when_dataset_missing() -> None:
    from mcp_server.application.agents.rag_validation.test_dataset_loader import (
        TestDatasetNotFoundError,
    )

    client = TestClient(create_local_ui_app())

    with patch(
        "mcp_server.application.agents.rag_validation.test_dataset_loader.summarize_test_dataset",
        side_effect=TestDatasetNotFoundError("Test dataset data directory not found"),
    ):
        response = client.get("/api/benchmarks/rag/test-dataset-summary")

    assert response.status_code == 503
    assert "Test dataset data directory not found" in response.json()["detail"]


def test_get_rag_optimization_report_returns_404_when_missing() -> None:
    client = TestClient(create_local_ui_app())

    with patch(
        "mcp_server.application.agents.rag_validation.optimization_report.load_optimization_report",
        return_value=None,
    ):
        response = client.get("/api/benchmarks/rag/optimization-report")

    assert response.status_code == 404


def test_get_rag_optimization_report_returns_saved_report() -> None:
    from mcp_server.domain.optimization_report import (
        OptimizationDiff,
        OptimizationPhaseResult,
        RagOptimizationReport,
        ScenarioOptimizationRow,
    )
    from mcp_server.domain.rag_hyperparameters import RagHyperparameters

    hyperparameters = RagHyperparameters(
        retrieval_mode="vector",
        retrieve_limit=8,
        rerank_enabled=False,
        rerank_top_n=6,
    )
    row = ScenarioOptimizationRow(
        scenario_name="SC0001",
        query="How do I authenticate?",
        phrase_coverage=0.5,
        first_phrase_rank_reciprocal=0.5,
        gold_semantic_relevance=0.42,
        gold_semantic_precision=0.25,
        validation_passed=False,
    )
    phase = OptimizationPhaseResult(
        hyperparameters=hyperparameters,
        mean_phrase_coverage=0.5,
        mean_first_phrase_rank_reciprocal=0.5,
        mean_gold_semantic_relevance=0.42,
        mean_gold_semantic_precision=0.25,
        validation_pass_rate=0.0,
        scenarios=(row,),
    )
    report = RagOptimizationReport(
        created_at="2026-07-22T20:00:00+00:00",
        scenario_count=1,
        before=phase,
        after=OptimizationPhaseResult(
            hyperparameters=hyperparameters,
            mean_phrase_coverage=1.0,
            mean_first_phrase_rank_reciprocal=1.0,
            mean_gold_semantic_relevance=0.81,
            mean_gold_semantic_precision=0.75,
            validation_pass_rate=1.0,
            scenarios=(
                ScenarioOptimizationRow(
                    scenario_name="SC0001",
                    query="How do I authenticate?",
                    phrase_coverage=1.0,
                    first_phrase_rank_reciprocal=1.0,
                    gold_semantic_relevance=0.81,
                    gold_semantic_precision=0.75,
                    validation_passed=True,
                ),
            ),
        ),
        diff=OptimizationDiff(
            mean_phrase_coverage_delta=0.5,
            mean_first_phrase_rank_reciprocal_delta=0.5,
            mean_gold_semantic_relevance_delta=0.39,
            mean_gold_semantic_precision_delta=0.5,
            validation_pass_rate_delta=1.0,
        ),
        optimized_at="2026-07-22T20:05:00+00:00",
        objective="mean_phrase_coverage",
    )

    client = TestClient(create_local_ui_app())

    with patch(
        "mcp_server.application.agents.rag_validation.optimization_report.load_optimization_report",
        return_value=report,
    ):
        response = client.get("/api/benchmarks/rag/optimization-report")

    assert response.status_code == 200
    body = response.json()
    assert body["scenario_count"] == 1
    assert body["after"]["mean_phrase_coverage"] == 1.0
    assert body["diff"]["mean_phrase_coverage_delta"] == 0.5


def test_post_rag_optimize_streams_mocked_progress() -> None:
    from mcp_server.application.benchmark_runner import (
        RagOptimizationCompleteEvent,
        RagOptimizationProgressEvent,
    )

    async def _mock_stream(**_kwargs: object):
        yield RagOptimizationProgressEvent(
            stage="baseline",
            progress=5,
            message="Running baseline benchmarks across 1 scenario(s)…",
            scenario_count=1,
        )
        yield RagOptimizationCompleteEvent(
            stage="complete",
            progress=100,
            message="Hyperparameter optimization complete",
            report={
                "scenario_count": 1,
                "before": {"mean_phrase_coverage": 0.5},
                "after": {"mean_phrase_coverage": 1.0},
                "diff": {"mean_phrase_coverage_delta": 0.5},
            },
            optimized_hyperparameters={"retrieve_limit": 8},
        )

    client = TestClient(create_local_ui_app())

    with patch(
        "mcp_server.interface.local_ui.api.stream_rag_optimization",
        _mock_stream,
    ):
        with client.stream(
            "POST",
            "/api/benchmarks/rag/optimize",
            json={"max_scenarios": 1},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")

            events: list[dict[str, Any]] = []
            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    block, buffer = buffer.split("\n\n", 1)
                    for line in block.splitlines():
                        if line.startswith("data: "):
                            events.append(json.loads(line[6:]))

    assert events[0]["stage"] == "baseline"
    assert events[-1]["stage"] == "complete"
    assert events[-1]["report"]["after"]["mean_phrase_coverage"] == 1.0


def test_post_rag_optimize_rejects_invalid_max_scenarios() -> None:
    client = TestClient(create_local_ui_app())

    response = client.post(
        "/api/benchmarks/rag/optimize",
        json={"max_scenarios": 0},
    )

    assert response.status_code == 422
