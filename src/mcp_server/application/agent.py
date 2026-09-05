"""LangChain agent and LangGraph workflow definitions."""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from mcp_server.application.agents.content_generation.graph import (
    get_content_generation_graph,
    reset_content_generation_graph_cache,
)
from mcp_server.application.agents.course_scaffold.graph import (
    get_course_scaffold_graph,
    reset_course_scaffold_graph_cache,
)
from mcp_server.application.agents.project_review.graph import (
    get_project_review_graph,
    reset_project_review_graph_cache,
)
from mcp_server.application.agents.research_article.graph import (
    get_research_article_graph,
    reset_research_article_graph_cache,
)
from mcp_server.application.agents.socratic.graph import (
    get_socratic_tutor_graph,
    reset_socratic_tutor_graph_cache,
)
from mcp_server.application.agents.tavily_search.graph import (
    get_tavily_search_graph,
    reset_tavily_search_graph_cache,
)
from mcp_server.application.agents.youtube_search.graph import (
    get_youtube_search_graph,
    reset_youtube_search_graph_cache,
)
from mcp_server.application.workflow_config import (
    DEFAULT_WORKFLOW_EXECUTION_CONFIG,
    WorkflowExecutionConfig,
    get_workflow_execution_config,
    read_node_retry_policy,
)
from mcp_server.application.workflow_graph import RegisteredWorkflow


def _workflow_runtime_config() -> WorkflowExecutionConfig:
    """Return runtime config, falling back to repo-root defaults when not initialized."""
    try:
        return get_workflow_execution_config()
    except RuntimeError:
        return DEFAULT_WORKFLOW_EXECUTION_CONFIG


def _node_retry_policy() -> RetryPolicy:
    config = _workflow_runtime_config()
    max_attempts = max(config.node_retries + 1, 1)
    return RetryPolicy(max_attempts=max_attempts)


def _read_node_retry_policy() -> RetryPolicy:
    """Read-only external port nodes fail fast — no automatic retries."""
    return read_node_retry_policy()


def _node_timeout_seconds() -> float:
    return _workflow_runtime_config().agent_node_timeout_seconds


def workflow_timeout_seconds() -> float:
    """Return the configured overall workflow execution timeout."""
    return _workflow_runtime_config().workflow_timeout_seconds


async def ainvoke_with_workflow_timeout(
    graph: CompiledStateGraph[Any, Any, Any],
    state: Any,
    *,
    config: RunnableConfig | None = None,
    timeout_seconds: float | None = None,
) -> Any:
    """Invoke a compiled graph with the configured workflow timeout."""
    result = await asyncio.wait_for(
        graph.ainvoke(state, config=config),
        timeout=timeout_seconds if timeout_seconds is not None else workflow_timeout_seconds(),
    )
    return result




_REGISTERED_WORKFLOWS: list[RegisteredWorkflow] | None = None


def _build_registered_workflows() -> list[RegisteredWorkflow]:
    return [
        RegisteredWorkflow(
            id="tavily-search",
            name="Tavily Web Search",
            description="Run a simple Tavily web search and return normalized result snippets.",
            graph=get_tavily_search_graph(),
        ),
        RegisteredWorkflow(
            id="youtube-search",
            name="YouTube Video Search",
            description="Search YouTube for educational videos matching a query.",
            graph=get_youtube_search_graph(),
        ),
        RegisteredWorkflow(
            id="research-article",
            name="Research → Journalistic Article",
            description=(
                "An agent plans research, orchestrates parallel Tavily and YouTube tool calls, "
                "merges both contexts, and writes a journalistic article."
            ),
            graph=get_research_article_graph(),
        ),
        RegisteredWorkflow(
            id="content-generation",
            name="Lesson → Quiz + PBL",
            description=(
                "Generate a structured lesson with Groq, then derive a quiz and "
                "problem-based learning project with validation retries and model fallback."
            ),
            graph=get_content_generation_graph(),
        ),
        RegisteredWorkflow(
            id="course-scaffold",
            name="Course Scaffold",
            description=(
                "Generate a structure-only course graph (nodes and edges) from a "
                "teacher prompt. Does not write README, quiz, or project bodies."
            ),
            graph=get_course_scaffold_graph(),
        ),
        RegisteredWorkflow(
            id="project-review",
            name="Project Delivery Review",
            description=(
                "Collect project README/starter/last deliveries, grade 0–100 with Groq, "
                "validate comment rules, and persist via grade-project-delivery."
            ),
            graph=get_project_review_graph(),
        ),
        RegisteredWorkflow(
            id="socratic-tutor",
            name="Socratic Tutor",
            description=(
                "Hint-ladder tutoring grounded in catalog/graph from the backend. "
                "Never assigns grades or project scores."
            ),
            graph=get_socratic_tutor_graph(),
        ),
    ]


def list_registered_workflows() -> list[RegisteredWorkflow]:
    """Return all LangGraph workflows exposed to the local UI."""
    global _REGISTERED_WORKFLOWS
    if _REGISTERED_WORKFLOWS is None:
        _REGISTERED_WORKFLOWS = _build_registered_workflows()
    return _REGISTERED_WORKFLOWS


def reset_registered_workflows_cache() -> None:
    """Clear cached workflow list (for tests)."""
    global _REGISTERED_WORKFLOWS
    _REGISTERED_WORKFLOWS = None
    reset_content_generation_graph_cache()
    reset_course_scaffold_graph_cache()
    reset_project_review_graph_cache()
    reset_socratic_tutor_graph_cache()
    reset_tavily_search_graph_cache()
    reset_youtube_search_graph_cache()
    reset_research_article_graph_cache()
