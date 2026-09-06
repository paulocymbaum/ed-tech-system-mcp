"""Regression: graph-scoped harness drafts must map into ContentGenerationRunResponse."""

from mcp_server.application.content_generation_dtos import content_generation_state_to_run_response
from mcp_server.domain.harness_schemas import (
    HarnessLessonDraft,
    HarnessProjectDraft,
    HarnessProjectFile,
    HarnessQuizDraft,
    HarnessQuizOption,
    HarnessQuizQuestion,
    HarnessTestCase,
    LessonMetaDraft,
)


def test_graph_scoped_harness_drafts_coerce_to_response() -> None:
    lesson = HarnessLessonDraft(
        readme_markdown="# Variables\n\nLearn what a variable stores and why names matter.\n",
        meta=LessonMetaDraft(
            id="variables",
            graphIndex="1.2.3",
            graphNodeId="11111111-1111-1111-1111-111111111111",
            title="Variables",
            status="draft",
        ),
    )
    quiz = HarnessQuizDraft(
        id="variables-quiz",
        title="Variables check",
        questions=[
            HarnessQuizQuestion(
                id="q1",
                prompt="What is a variable?",
                options=[
                    HarnessQuizOption(id="a", text="A named storage location"),
                    HarnessQuizOption(id="b", text="A loop"),
                    HarnessQuizOption(id="c", text="A database table"),
                    HarnessQuizOption(id="d", text="A network request"),
                ],
                correctOptionId="a",
                explanation="Variables hold values under a name.",
            )
        ],
    )
    project = HarnessProjectDraft(
        slug="variables-lab",
        title="Variables lab",
        root_path="modules/_cms/variables-lab/",
        readme_markdown="# Lab\n\nWrite a program that stores a number.\n",
        files=[HarnessProjectFile(path="index.js", kind="starter", content="const x = 1;\n")],
        test_cases=[
            HarnessTestCase(
                id="smoke",
                name="smoke",
                stdin="",
                expectedStdout="",
                expectedExitCode=0,
            )
        ],
    )

    response = content_generation_state_to_run_response(
        {
            "topic": "variables",
            "grade_level": "6th grade",
            "graph_scoped": True,
            "tenant_id": "8d9cad71-55db-43e4-87f3-89b9077c174f",
            "course_slug": "javascript",
            "generation_complete": True,
            "lesson_retry_count": 0,
            "quiz_retry_count": 0,
            "pbl_retry_count": 0,
            "lesson": lesson,
            "quiz": quiz,
            "pbl": project,
            "harness_lesson": lesson,
            "harness_quiz": quiz,
            "harness_project": project,
            "lesson_validation_errors": [],
            "quiz_validation_errors": [],
            "pbl_validation_errors": [],
        }
    )

    assert response.graph_scoped is True
    assert isinstance(response.lesson, dict)
    assert isinstance(response.quiz, dict)
    assert isinstance(response.pbl, dict)
    assert isinstance(response.harness_lesson, dict)
    assert response.harness_lesson["meta"]["title"] == "Variables"
    # Validators + FE expect camelCase graph keys (aliases), not snake_case fields.
    assert response.harness_lesson["meta"]["graphIndex"] == "1.2.3"
    assert response.harness_lesson["meta"]["graphNodeId"] == "11111111-1111-1111-1111-111111111111"
    assert "graph_index" not in response.harness_lesson["meta"]
    assert response.harness_quiz is not None
    assert response.harness_quiz["questions"][0]["correctOptionId"] == "a"
    assert response.harness_project is not None
