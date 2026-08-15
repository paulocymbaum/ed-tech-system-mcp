"""EdHarness-aligned draft schemas for graph-scoped authoring (E6.3)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator


class LessonMetaDraft(BaseModel):
    """``lesson.meta.json`` fields produced during generation."""

    id: str = Field(min_length=1)
    graph_index: str = Field(min_length=1, alias="graphIndex")
    graph_node_id: str = Field(min_length=1, alias="graphNodeId")
    title: str = Field(min_length=1)
    description: str | None = None
    lesson_dependencies: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    status: str = "draft"

    model_config = {"populate_by_name": True}


class HarnessLessonDraft(BaseModel):
    """Lesson README + meta aligned with EdHarness disk layout."""

    readme_markdown: str = Field(min_length=20)
    meta: LessonMetaDraft


class HarnessQuizOption(BaseModel):
    """Quiz option with slug id (maps to RPC ``slug``)."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class HarnessQuizQuestion(BaseModel):
    """Quiz question with slug ids and ``correctOptionId``."""

    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    options: list[HarnessQuizOption] = Field(min_length=2, max_length=6)
    correct_option_id: str = Field(min_length=1, alias="correctOptionId")
    explanation: str | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def correct_option_exists(self) -> Self:
        option_ids = {option.id for option in self.options}
        if self.correct_option_id not in option_ids:
            msg = "correctOptionId must match one of the option ids"
            raise ValueError(msg)
        return self


class HarnessQuizDraft(BaseModel):
    """``quiz/quiz.json`` shape for catalog + ``upsert_quiz_tree``."""

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    lesson_id: str | None = Field(default=None, alias="lessonId")
    graph_index: str | None = Field(default=None, alias="graphIndex")
    questions: list[HarnessQuizQuestion] = Field(min_length=1, max_length=20)

    model_config = {"populate_by_name": True}


class HarnessProjectFile(BaseModel):
    """Starter/solution file in project tree."""

    path: str = Field(min_length=1)
    kind: str = Field(default="starter")
    content: str | None = None


class HarnessTestCase(BaseModel):
    """One ``starter/tests.json`` case."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    stdin: str = ""
    expected_stdout: str | None = Field(default=None, alias="expectedStdout")
    expected_exit_code: int | None = Field(default=None, alias="expectedExitCode")

    model_config = {"populate_by_name": True}


class HarnessProjectDraft(BaseModel):
    """PBL project with README, files, and test cases."""

    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    graph_index: str | None = None
    root_path: str = Field(min_length=1)
    readme_markdown: str = Field(min_length=20)
    files: list[HarnessProjectFile] = Field(min_length=1)
    test_cases: list[HarnessTestCase] = Field(min_length=1)
