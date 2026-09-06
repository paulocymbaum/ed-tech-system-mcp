"""Stamp Teach-resolved graph ids onto harness drafts after LLM parse."""

from mcp_server.application.agents.content_generation.nodes import (
    stamp_harness_lesson_identity,
    stamp_harness_quiz_identity,
)
from mcp_server.application.agents.content_generation.prompts import lesson_user_prompt
from mcp_server.application.agents.content_generation.state import ContentGenerationState
from mcp_server.domain.authoring import GraphNodeHit
from mcp_server.domain.harness_schemas import (
    HarnessLessonDraft,
    HarnessQuizDraft,
    HarnessQuizOption,
    HarnessQuizQuestion,
    LessonMetaDraft,
)


def _lesson() -> HarnessLessonDraft:
    return HarnessLessonDraft(
        readme_markdown="# Title\n\n## Overview\n\nTeaching body with enough text.\n",
        meta=LessonMetaDraft(
            id="llm-invented",
            graphIndex="99.9",
            graphNodeId="wrong-node",
            title="Title",
        ),
    )


def test_stamp_harness_lesson_identity_prefers_state_and_hit_index() -> None:
    state: ContentGenerationState = {
        "topic": "Variables",
        "grade_level": "6th grade",
        "lesson_slug": "01-variables",
        "graph_node_id": "11111111-1111-4111-8111-111111111111",
        "graph_hits": [
            GraphNodeHit(
                node_id="11111111-1111-4111-8111-111111111111",
                course_slug="javascript",
                course_title="JS",
                label="Variables",
                graph_index="01.1",
                kind="lesson",
                score=1.0,
            )
        ],
    }
    stamped = stamp_harness_lesson_identity(_lesson(), state)
    assert stamped.meta.id == "01-variables"
    assert stamped.meta.graph_node_id == "11111111-1111-4111-8111-111111111111"
    assert stamped.meta.graph_index == "01.1"
    assert stamped.meta.title == "Title"


def test_stamp_harness_quiz_identity_sets_lesson_slug_and_index() -> None:
    quiz = HarnessQuizDraft(
        id="quiz",
        title="Check",
        questions=[
            HarnessQuizQuestion(
                id="q1",
                prompt="What?",
                options=[
                    HarnessQuizOption(id="a", text="A"),
                    HarnessQuizOption(id="b", text="B"),
                    HarnessQuizOption(id="c", text="C"),
                    HarnessQuizOption(id="d", text="D"),
                ],
                correctOptionId="a",
            )
        ],
    )
    state: ContentGenerationState = {
        "topic": "Variables",
        "grade_level": "6th grade",
        "lesson_slug": "01-variables",
        "graph_node_id": "11111111-1111-4111-8111-111111111111",
        "graph_hits": [
            GraphNodeHit(
                node_id="11111111-1111-4111-8111-111111111111",
                course_slug="javascript",
                course_title="JS",
                label="Variables",
                graph_index="01.1",
                kind="lesson",
                score=1.0,
            )
        ],
    }
    stamped = stamp_harness_quiz_identity(quiz, state)
    assert stamped.lesson_id == "01-variables"
    assert stamped.graph_index == "01.1"


def test_lesson_user_prompt_forbids_question_lists() -> None:
    prompt = lesson_user_prompt(
        topic="Loops. Lesson with predict-first quiz.",
        grade_level="6th grade",
        validation_errors=None,
        graph_scoped=True,
        graph_node_id="n1",
        lesson_slug="loops",
    )
    assert "questions array" in prompt
    assert "README only" in prompt
