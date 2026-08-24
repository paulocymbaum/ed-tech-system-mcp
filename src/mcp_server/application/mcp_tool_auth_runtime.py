"""Runtime flags for MCP HTTP inbound token and privileged-tool JWT checks."""

from __future__ import annotations

from dataclasses import dataclass

from mcp_server.domain.caller_identity import CallerIdentityPort

CALLER_JWT_HEADER = "x-edharness-caller-jwt"

PRIVILEGED_TOOLS = frozenset(
    {
        "build_lesson_enrichment_query",
        "search_youtube",
        "collect_project_review_context",
        "project_review",
        "socratic_tutor",
        "search_graph_nodes",
        "save_to_backend",
        "author_lesson_pipeline",
        "content_generation",
        "research_article",
    }
)


@dataclass(frozen=True)
class McpToolAuthRuntime:
    require_caller_jwt: bool
    identity: CallerIdentityPort | None


_runtime: McpToolAuthRuntime | None = None


def set_mcp_tool_auth_runtime(runtime: McpToolAuthRuntime | None) -> None:
    global _runtime
    _runtime = runtime


def get_mcp_tool_auth_runtime() -> McpToolAuthRuntime | None:
    return _runtime
