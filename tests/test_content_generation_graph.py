"""Tests for the lesson → quiz + PBL content-generation LangGraph workflow."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import SecretStr

from mcp_server.application.agent import list_registered_workflows, reset_registered_workflows_cache
from mcp_server.application.agents.content_generation.graph import (
    build_content_generation_graph,
    reset_content_generation_graph_cache,
    run_content_generation_graph,
)
from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.application.llm_router import LLMRouter
from mcp_server.application.routing_chat_model import RoutingChatModel
from mcp_server.application.workflow_config import (
    WorkflowExecutionConfig,
    reset_workflow_execution_config,
    set_workflow_execution_config,
)
from mcp_server.domain.content_schemas import LessonDraft, PBLDraft, QuizDraft
from mcp_server.domain.llm_routing import (
    GroqModelRecord,
    IGroqModelRegistry,
    ILLMDebounceGate,
    LLMComplexity,
    is_developer_plan_groq_model,
)


def _lesson_payload(*, topic: str, grade_level: str) -> dict[str, object]:
    return {
        "title": f"Lesson: {topic}",
        "topic": topic,
        "grade_level": grade_level,
        "objectives": [f"Understand {topic}"],
        "sections": [
            {"heading": "Introduction", "content": "This section introduces the core ideas."},
            {"heading": "Practice", "content": "Students apply the concept with guided examples."},
        ],
        "summary": "Students leave with a working understanding of the topic.",
    }


def _quiz_payload(*, topic: str) -> dict[str, object]:
    return {
        "title": f"Quiz: {topic}",
        "questions": [
            {
                "question": f"What is {topic}?",
                "options": ["A definition", "A color", "A shape"],
                "correct_answer": "A definition",
                "explanation": "The topic is a concept, not a color or shape.",
            },
            {
                "question": f"Why study {topic}?",
                "options": ["It builds understanding", "It is random", "It is unused"],
                "correct_answer": "It builds understanding",
                "explanation": "The lesson explains why the topic matters.",
            },
            {
                "question": f"How do you practice {topic}?",
                "options": ["With examples", "By ignoring it", "By guessing"],
                "correct_answer": "With examples",
                "explanation": "Practice comes from guided examples.",
            },
        ],
    }


def _pbl_payload(*, topic: str) -> dict[str, object]:
    return {
        "title": f"PBL: {topic}",
        "driving_question": f"How can we apply {topic} to solve a real problem?",
        "scenario": (
            "A local community group needs help applying the concept in a meaningful project "
            "that benefits their neighborhood."
        ),
        "learning_objectives": [f"Apply {topic} in an authentic context"],
        "deliverables": [
            {
                "name": "Project plan",
                "description": "A written plan describing the approach and expected outcomes.",
            }
        ],
        "duration_days": 5,
    }


class InMemoryGroqModelRegistry(IGroqModelRegistry):
    def __init__(self, model_ids: list[str]) -> None:
        self._records = {
            model_id: GroqModelRecord(
                model_id=model_id,
                display_name=model_id,
                active=True,
                is_free=True,
                is_developer_plan=is_developer_plan_groq_model(model_id),
                is_routable=True,
                complexity=frozenset({1, 2, 3}),
            )
            for model_id in model_ids
        }

    def refresh_active_models(self) -> None:
        return

    def refresh_from_catalog(self) -> None:
        return

    def list_records(self) -> list[GroqModelRecord]:
        return list(self._records.values())

    def get_active_model_ids(self) -> list[str]:
        return sorted(record.model_id for record in self._records.values() if record.active)

    def get_active_model_ids_for_complexity(self, complexity: LLMComplexity) -> list[str]:
        tier = int(complexity)
        return sorted(
            record.model_id
            for record in self._records.values()
            if record.active and tier in record.complexity
        )

    def deactivate_until(self, model_id: str, until: datetime) -> None:
        record = self._records.get(model_id)
        if record is None:
            return
        self._records[model_id] = GroqModelRecord(
            model_id=model_id,
            display_name=record.display_name,
            active=False,
            is_free=record.is_free,
            is_developer_plan=record.is_developer_plan,
            is_routable=record.is_routable,
            deactivated_until=until,
            complexity=record.complexity,
        )

    def is_known_model(self, model_id: str) -> bool:
        return model_id in self._records


class NoOpDebounceGate(ILLMDebounceGate):
    def acquire_sync(self, complexity: LLMComplexity = LLMComplexity.MEDIUM) -> None:
        del complexity
        return

    async def acquire(self, complexity: LLMComplexity = LLMComplexity.MEDIUM) -> None:
        del complexity
        return


class ScriptedContentModel(BaseChatModel):
    """Returns structured JSON payloads based on prompt keywords."""

    lesson_attempts: int = 0
    quiz_attempts: int = 0
    pbl_attempts: int = 0
    fail_first_lesson: bool = False

    @property
    def _llm_type(self) -> str:
        return "scripted-content"

    def _payload_for_messages(self, messages: list[BaseMessage]) -> str:
        text = "\n".join(str(message.content) for message in messages)
        if "quiz" in text.lower() and "assessment" in text.lower():
            self.quiz_attempts += 1
            return json.dumps(_quiz_payload(topic="fractions"))
        if "problem-based learning" in text.lower() or "pbl" in text.lower():
            self.pbl_attempts += 1
            return json.dumps(_pbl_payload(topic="fractions"))
        self.lesson_attempts += 1
        if self.fail_first_lesson and self.lesson_attempts == 1:
            return '{"title":"bad lesson","topic":"fractions"}'
        return json.dumps(_lesson_payload(topic="fractions", grade_level="6th grade"))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = self._payload_for_messages(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=payload))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    reset_registered_workflows_cache()
    reset_content_generation_graph_cache()
    reset_workflow_execution_config()
    reset_chat_model()
    set_workflow_execution_config(
        WorkflowExecutionConfig(
            node_retries=2,
            workflow_timeout_seconds=30.0,
            agent_node_timeout_seconds=10.0,
        )
    )


def test_content_generation_workflow_is_registered() -> None:
    workflows = list_registered_workflows()
    workflow_ids = {workflow.id for workflow in workflows}

    assert "content-generation" in workflow_ids
    content = next(workflow for workflow in workflows if workflow.id == "content-generation")
    assert "lesson" in content.description.lower()
    assert "quiz" in content.description.lower()


def test_content_generation_graph_exposes_validation_nodes() -> None:
    graph = build_content_generation_graph()
    drawable = graph.get_graph()
    node_ids = set(drawable.nodes)

    assert "generate_lesson" in node_ids
    assert "validate_lesson" in node_ids
    assert "generate_quiz" in node_ids
    assert "validate_quiz" in node_ids
    assert "generate_pbl" in node_ids
    assert "validate_pbl" in node_ids
    assert "merge_results" in node_ids


async def test_content_generation_graph_runs_lesson_quiz_and_pbl() -> None:
    model = ScriptedContentModel()
    set_chat_model(model)

    result = await run_content_generation_graph("fractions", grade_level="6th grade")

    assert result.get("generation_complete") is True
    assert isinstance(result.get("lesson"), LessonDraft)
    assert isinstance(result.get("quiz"), QuizDraft)
    assert isinstance(result.get("pbl"), PBLDraft)
    assert result["lesson"].topic == "fractions"
    assert len(result["quiz"].questions) >= 3
    assert result["pbl"].duration_days == 5


async def test_content_generation_retries_lesson_validation_before_success() -> None:
    model = ScriptedContentModel(fail_first_lesson=True)
    set_chat_model(model)

    result = await run_content_generation_graph("fractions", grade_level="6th grade")

    assert model.lesson_attempts == 2
    assert result.get("lesson_retry_count", 0) == 1
    assert isinstance(result.get("lesson"), LessonDraft)
    assert isinstance(result.get("quiz"), QuizDraft)
    assert isinstance(result.get("pbl"), PBLDraft)


async def test_content_generation_uses_routing_chat_model_for_fallback() -> None:
    class FailingThenOkModel(BaseChatModel):
        model_id: str
        fail: bool = False
        calls: int = 0

        @property
        def _llm_type(self) -> str:
            return "failing-content-stub"

        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            self.calls += 1
            if self.fail:
                raise RuntimeError("provider unavailable")
            scripted = ScriptedContentModel()
            return scripted._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

        async def _agenerate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def builder(api_key: SecretStr, model_id: str, temperature: float) -> BaseChatModel:
        _ = api_key, temperature
        return FailingThenOkModel(model_id=model_id, fail=model_id == "llama-3.1-8b-instant")

    router = LLMRouter(
        api_key=SecretStr("test"),
        temperature=0.0,
        registry=InMemoryGroqModelRegistry(["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]),
        debounce_gate=NoOpDebounceGate(),
        model_builder=builder,
        default_complexity=LLMComplexity.MEDIUM,
    )
    set_chat_model(RoutingChatModel(router, default_complexity=LLMComplexity.MEDIUM))

    result = await run_content_generation_graph("fractions", grade_level="6th grade")

    assert isinstance(result.get("lesson"), LessonDraft)
    assert isinstance(result.get("quiz"), QuizDraft)
    assert isinstance(result.get("pbl"), PBLDraft)
