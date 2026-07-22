"""Domain entity contract tests (T01–T06)."""

import pytest
from pydantic import ValidationError

from mcp_server.domain.schemas import DocumentHit, VideoResult


def test_t01_video_result_happy_path() -> None:
    result = VideoResult(
        title="Intro to Algebra",
        channel="Math Academy",
        url="https://example.com/video",
    )
    assert result.title == "Intro to Algebra"
    assert result.channel == "Math Academy"
    assert result.url == "https://example.com/video"


def test_t02_video_result_default_relevance_score() -> None:
    result = VideoResult(title="T", channel="C", url="https://example.com")
    assert result.relevance_score == 0.0


def test_t03_video_result_relevance_score_bounds() -> None:
    with pytest.raises(ValidationError):
        VideoResult(title="T", channel="C", url="https://example.com", relevance_score=-0.1)
    with pytest.raises(ValidationError):
        VideoResult(title="T", channel="C", url="https://example.com", relevance_score=1.1)


def test_t04_video_result_optional_duration() -> None:
    result = VideoResult(title="T", channel="C", url="https://example.com")
    assert result.duration_seconds is None


def test_t05_document_hit_happy_path() -> None:
    hit = DocumentHit(id="doc-1", title="Lesson 1", content="Body text")
    assert hit.id == "doc-1"
    assert hit.title == "Lesson 1"
    assert hit.content == "Body text"


def test_t06_document_hit_metadata_defaults_empty() -> None:
    hit = DocumentHit(id="doc-1", title="Lesson 1", content="Body text")
    assert hit.metadata == {}
