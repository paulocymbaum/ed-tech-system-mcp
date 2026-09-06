"""Tests for workflow execution tracing."""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from mcp_server.application.agents.content_generation.graph import (
    build_content_generation_graph,
    initial_content_generation_state,
)
from mcp_server.application.llm import reset_chat_model, set_chat_model
from mcp_server.application.token_counting_runtime import reset_token_counter, set_token_counter
from mcp_server.application.workflow_trace import (
    GraphStreamComplete,
    WorkflowTraceStart,
    WorkflowTraceStep,
    invoke_graph_with_trace,
    stream_graph_with_trace,
)
from mcp_server.infrastructure.token_counting.tiktoken_counter import TiktokenTokenCounter


class ScriptedContentModel(BaseChatModel):
    lesson_attempts: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-content"

    def _payload_for_messages(self, messages: list[BaseMessage]) -> str:
        text = "\n".join(str(message.content) for message in messages)
        if (
            "quiz" in text.lower()
            and "assessment" in text.lower()
            and "create a lesson" not in text.lower()
        ):
            return json.dumps(
                {
                    "title": "Quiz",
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
            )
        if (
            "problem-based learning" in text.lower()
            and "create a lesson" not in text.lower()
        ):
            return json.dumps(
                {
                    "title": "PBL",
                    "driving_question": "How can we apply this?",
                    "scenario": "A realistic scenario with enough detail for validation.",
                    "learning_objectives": ["Apply the concept"],
                    "deliverables": [
                        {
                            "name": "Plan",
                            "description": "A written project plan with milestones.",
                        }
                    ],
                    "duration_days": 5,
                }
            )
        self.lesson_attempts += 1
        if self.lesson_attempts == 1:
            return '{"title":"bad lesson"}'
        return json.dumps(
            {
                "title": "Lesson",
                "topic": "fractions",
                "grade_level": "6th grade",
                "objectives": ["Understand fractions"],
                "sections": [
                    {"heading": "Intro", "content": "Fractions represent parts of a whole."},
                    {"heading": "Practice", "content": "Students solve guided fraction problems."},
                ],
                "summary": "Students understand fractions as parts of a whole.",
            }
        )

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
    reset_chat_model()
    reset_token_counter()
    set_token_counter(TiktokenTokenCounter())


async def test_invoke_graph_with_trace_records_retries_and_failures() -> None:
    set_chat_model(ScriptedContentModel())
    graph = build_content_generation_graph()
    state = initial_content_generation_state("fractions", grade_level="6th grade")

    final_state, trace = await invoke_graph_with_trace(graph, state, timeout_seconds=30.0)

    assert final_state.get("generation_complete") is True
    lesson_steps = [step for step in trace if step.node_id == "generate_lesson"]
    assert len(lesson_steps) == 2
    assert lesson_steps[0].status == "failed"
    assert lesson_steps[1].status == "ok"
    retry_steps = [step for step in trace if step.status == "retry"]
    assert any(step.retry_counts.get("lesson_retry_count") == 1 for step in retry_steps)
    assert trace[0].input_snapshot["topic"] == "fractions"
    assert trace[0].llm_io is not None
    assert trace[0].llm_io["model_name"] == "scripted-content"
    assert trace[0].input_snapshot["llm_request"]["model_name"] == "scripted-content"
    assert trace[0].output_update["model_name"] == "scripted-content"
    assert "system_prompt" in trace[0].llm_io
    assert trace[0].llm_io["input_tokens"] > 0
    assert trace[0].llm_io["output_tokens"] > 0
    assert trace[0].llm_io["total_tokens"] == (
        trace[0].llm_io["input_tokens"] + trace[0].llm_io["output_tokens"]
    )
    assert trace[0].input_snapshot["llm_request"]["input_tokens"] > 0
    assert trace[0].output_update["total_tokens"] > 0
    assert trace[0].output_update.get("lesson_validation_errors")


async def test_stream_graph_with_trace_yields_steps_then_complete() -> None:
    set_chat_model(ScriptedContentModel())
    graph = build_content_generation_graph()
    state = initial_content_generation_state("fractions", grade_level="6th grade")

    items: list[WorkflowTraceStep | GraphStreamComplete] = []
    async for item in stream_graph_with_trace(graph, state, timeout_seconds=30.0):
        items.append(item)

    step_items = [item for item in items if isinstance(item, WorkflowTraceStep)]
    complete_items = [item for item in items if isinstance(item, GraphStreamComplete)]
    assert step_items
    assert len(complete_items) == 1
    assert items[-1] is complete_items[0]


class _StartThenUpdateGraph:
    async def astream(self, state: Any, stream_mode: object = "updates"):
        del stream_mode
        yield ("debug", {"type": "task", "payload": {"name": "generate_lesson"}})
        yield ("updates", {"generate_lesson": {"ok": True, "topic": state["topic"]}})


async def test_stream_graph_with_trace_yields_start_before_update() -> None:
    items: list[object] = []
    async for item in stream_graph_with_trace(
        _StartThenUpdateGraph(),  # type: ignore[arg-type]
        {"topic": "fractions"},
        timeout_seconds=5.0,
    ):
        items.append(item)
    assert isinstance(items[0], WorkflowTraceStart)
    assert items[0].node_id == "generate_lesson"
    assert isinstance(items[1], WorkflowTraceStep)
    assert items[1].node_id == "generate_lesson"


class _ValuesThenUpdateGraph:
    async def astream(self, state: Any, stream_mode: object = "updates"):
        del stream_mode
        yield ("debug", {"type": "task", "payload": {"name": "generate_lesson"}})
        yield ("updates", {"generate_lesson": {"partial": True}})
        yield (
            "values",
            {
                **state,
                "harness_lesson": {"readme_markdown": "# Body\n\n## Section\n"},
                "partial": True,
            },
        )


async def test_stream_graph_with_trace_values_replace_running_state() -> None:
    items: list[object] = []
    async for item in stream_graph_with_trace(
        _ValuesThenUpdateGraph(),  # type: ignore[arg-type]
        {"topic": "fractions"},
        timeout_seconds=5.0,
    ):
        items.append(item)
    complete = next(item for item in items if isinstance(item, GraphStreamComplete))
    assert complete.state["topic"] == "fractions"
    assert complete.state["harness_lesson"]["readme_markdown"].startswith("# Body")
    assert complete.state["partial"] is True



async def test_stream_graph_with_trace_matches_invoke_final_state() -> None:
    graph = build_content_generation_graph()
    state = initial_content_generation_state("fractions", grade_level="6th grade")

    set_chat_model(ScriptedContentModel())
    streamed_state = None
    streamed_trace: list[WorkflowTraceStep] = []
    async for item in stream_graph_with_trace(graph, state, timeout_seconds=30.0):
        if isinstance(item, GraphStreamComplete):
            streamed_state = item.state
            streamed_trace = item.trace

    set_chat_model(ScriptedContentModel())
    invoked_state, invoked_trace = await invoke_graph_with_trace(
        graph, state, timeout_seconds=30.0
    )

    assert streamed_state == invoked_state
    assert len(streamed_trace) == len(invoked_trace)
    assert [step.node_id for step in streamed_trace] == [
        step.node_id for step in invoked_trace
    ]


class _MultiKeyGraph:
    """LangGraph can emit more than one node update in a single ``updates`` chunk."""

    async def astream(self, state: Any, stream_mode: str = "updates"):
        del stream_mode
        yield {"generate_lesson": {"topic": state["topic"]}, "validate_lesson": {"ok": True}}
        yield {"save": {"generation_complete": True}}


async def test_stream_and_invoke_keep_every_node_in_a_multi_key_chunk() -> None:
    graph = _MultiKeyGraph()
    state = {"topic": "fractions"}

    invoked_state, invoked_trace = await invoke_graph_with_trace(
        graph,  # type: ignore[arg-type]
        state,
        timeout_seconds=5.0,
    )
    streamed: list[WorkflowTraceStep | GraphStreamComplete] = []
    async for item in stream_graph_with_trace(
        graph,  # type: ignore[arg-type]
        state,
        timeout_seconds=5.0,
    ):
        streamed.append(item)

    streamed_complete = next(item for item in streamed if isinstance(item, GraphStreamComplete))
    node_ids = [step.node_id for step in invoked_trace]
    assert node_ids == ["generate_lesson", "validate_lesson", "save"]
    assert [step.node_id for step in streamed_complete.trace] == node_ids
    assert invoked_state["generation_complete"] is True
    assert invoked_state["ok"] is True
    assert streamed_complete.state == invoked_state
