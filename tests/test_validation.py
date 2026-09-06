"""Interface validation schema contract tests (T08–T14)."""

import pytest
from pydantic import ValidationError

from mcp_server.application.content_generation_dtos import ContentGenerationRunRequest
from mcp_server.domain.schemas import VideoResult
from mcp_server.interface.validation import (
    VideoSearchRequest,
    VideoSearchResponse,
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


def test_content_generation_run_request_accepts_path_like_graph_node_id() -> None:
    request = ContentGenerationRunRequest(
        topic="Iterative Optimization",
        tenant_id="8d9cad71-55db-43e4-87f3-89b9077c174f",
        course_slug="javascript",
        module_id="6a04eed1-a967-5375-80cb-a5940a068084",
        lesson_slug="iterative-optimization",
        graph_node_id="lesson:javascript:07-technical-interview-preparation:07.5-iterative-optimization",
        graph_query="Iterative Optimization",
    )
    assert (
        request.graph_node_id
        == "lesson:javascript:07-technical-interview-preparation:07.5-iterative-optimization"
    )

