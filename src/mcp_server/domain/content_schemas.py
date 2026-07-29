"""Domain schemas for generated educational content."""

from typing import Self

from pydantic import BaseModel, Field, model_validator


class LessonSection(BaseModel):
    """A titled block within a generated lesson."""

    heading: str = Field(min_length=1)
    content: str = Field(min_length=10)


class LessonDraft(BaseModel):
    """Structured lesson plan produced by the content-generation workflow."""

    title: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    grade_level: str = Field(min_length=1)
    objectives: list[str] = Field(min_length=1)
    sections: list[LessonSection] = Field(min_length=1)
    summary: str = Field(min_length=10)


class QuizQuestion(BaseModel):
    """Single multiple-choice question."""

    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def correct_answer_in_options(self) -> Self:
        if self.correct_answer not in self.options:
            msg = "correct_answer must be one of the provided options"
            raise ValueError(msg)
        return self


class QuizDraft(BaseModel):
    """Quiz aligned to a generated lesson."""

    title: str = Field(min_length=1)
    questions: list[QuizQuestion] = Field(min_length=1, max_length=20)


class PBLDeliverable(BaseModel):
    """Expected student output for a PBL project."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=10)


class PBLDraft(BaseModel):
    """Problem-based learning project derived from a lesson."""

    title: str = Field(min_length=1)
    driving_question: str = Field(min_length=10)
    scenario: str = Field(min_length=20)
    learning_objectives: list[str] = Field(min_length=1)
    deliverables: list[PBLDeliverable] = Field(min_length=1)
    duration_days: int = Field(ge=1, le=30)
