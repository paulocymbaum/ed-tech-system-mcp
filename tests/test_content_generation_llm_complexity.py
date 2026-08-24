"""Author pipeline prefers faster Groq tiers on quiz/project steps."""

from __future__ import annotations

from mcp_server.application.agents.content_generation.graph import initial_content_generation_state
from mcp_server.application.agents.content_generation.nodes import (
    lesson_llm_complexity,
    quiz_pbl_llm_complexity,
)
from mcp_server.domain.llm_routing import LLMComplexity


def test_free_topic_run_keeps_high_lesson_and_medium_quiz_pbl() -> None:
    state = initial_content_generation_state("loops")
    assert state.get("fast_authoring") is not True
    assert lesson_llm_complexity(state) == LLMComplexity.HIGH
    assert quiz_pbl_llm_complexity(state) == LLMComplexity.MEDIUM


def test_author_pipeline_fast_profile_when_graph_module_and_slug() -> None:
    state = initial_content_generation_state(
        "Comments",
        tenant_id="00000000-0000-4000-8000-000000000001",
        course_slug="javascript",
        module_id="00000000-0000-4000-8000-000000000002",
        lesson_slug="comments",
    )
    assert state.get("fast_authoring") is True
    assert lesson_llm_complexity(state) == LLMComplexity.MEDIUM
    assert quiz_pbl_llm_complexity(state) == LLMComplexity.LOW
