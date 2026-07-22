"""Interface validation schema contract tests (T08–T14)."""

import pytest
from pydantic import ValidationError

from mcp_server.domain.schemas import DocumentHit, VideoResult
from mcp_server.interface.validation import (
    DocumentQueryRequest,
    DocumentSummary,
    VideoSearchRequest,
    VideoSearchResponse,
    WorkflowRunRequest,
    document_hit_to_summary,
    workflow_state_to_run_response,
)


def test_t08_video_search_request_happy_path() -> None:
    request = VideoSearchRequest(
        query="fractions",
        max_results=10,
        language="pt",
        safe_search=False,
    )
    assert request.query == "fractions"
    assert request.max_results == 10
    assert request.language == "pt"
    assert request.safe_search is False


def test_t09_video_search_request_defaults() -> None:
    request = VideoSearchRequest(query="algebra")
    assert request.max_results == 5
    assert request.language == "en"
    assert request.safe_search is True


def test_t10_video_search_request_empty_query() -> None:
    with pytest.raises(ValidationError):
        VideoSearchRequest(query="")


def test_t11_video_search_request_max_results_bounds() -> None:
    with pytest.raises(ValidationError):
        VideoSearchRequest(query="x", max_results=0)
    with pytest.raises(ValidationError):
        VideoSearchRequest(query="x", max_results=26)


def test_t12_video_search_request_language_length() -> None:
    with pytest.raises(ValidationError):
        VideoSearchRequest(query="x", language="a")
    with pytest.raises(ValidationError):
        VideoSearchRequest(query="x", language="a" * 11)


def test_t13_video_search_response_happy_path() -> None:
    videos = [
        VideoResult(title="V1", channel="C1", url="https://example.com/1"),
        VideoResult(title="V2", channel="C2", url="https://example.com/2"),
    ]
    response = VideoSearchResponse(videos=videos)
    assert len(response.videos) == 2
    assert all(isinstance(v, VideoResult) for v in response.videos)


def test_t14_video_search_response_empty_list() -> None:
    response = VideoSearchResponse(videos=[])
    assert response.videos == []


def test_t16_document_query_request_validation() -> None:
    with pytest.raises(ValidationError):
        DocumentQueryRequest(query="")
    with pytest.raises(ValidationError):
        DocumentQueryRequest(query="x", document_limit=0)
    with pytest.raises(ValidationError):
        DocumentQueryRequest(query="x", video_limit=26)


def test_t17_workflow_run_request_validation() -> None:
    with pytest.raises(ValidationError):
        WorkflowRunRequest(query="")
    with pytest.raises(ValidationError):
        WorkflowRunRequest(query="x", document_limit=51)
    with pytest.raises(ValidationError):
        WorkflowRunRequest(query="x", video_limit=0)


def test_t_rf10_workflow_state_to_run_response_maps_state_fields() -> None:
    documents = [
        DocumentHit(id="doc-1", title="Fractions", content="Full lesson body"),
    ]
    videos = [VideoResult(title="Video", channel="Ch", url="https://example.com")]
    state = {
        "query": "fractions",
        "search_terms": "Fractions",
        "document_count": 1,
        "video_count": 1,
        "documents": documents,
        "videos": videos,
    }

    response = workflow_state_to_run_response(state)

    assert response.query == "fractions"
    assert response.search_terms == "Fractions"
    assert response.document_count == 1
    assert response.video_count == 1
    assert len(response.documents) == 1
    assert response.documents[0].id == "doc-1"
    assert "Full lesson body" in response.documents[0].snippet
    assert "content" not in response.documents[0].model_dump()
    assert response.videos == videos


def test_t15_document_summary_prunes_content_to_snippet() -> None:
    hit = DocumentHit(
        id="doc-1",
        title="Algebra",
        content="x" * 250,
    )
    summary = document_hit_to_summary(hit, snippet_max_len=200)

    assert isinstance(summary, DocumentSummary)
    assert summary.id == "doc-1"
    assert summary.title == "Algebra"
    assert len(summary.snippet) == 203
    assert summary.snippet.endswith("...")
    dumped = summary.model_dump()
    assert set(dumped) == {"id", "title", "snippet"}
    assert "content" not in dumped
