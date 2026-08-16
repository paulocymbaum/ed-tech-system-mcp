"""M1/M2/M5: MCP tools skip full traces; warm uses embedding singleton."""

from __future__ import annotations

import inspect

from mcp_server.application.content_generation_runner import invoke_content_generation
from mcp_server.interface.custom_tools_agent_workflows import _invoke_research_article
from mcp_server.interface.custom_tools_project_review import project_review
from mcp_server.wiring import warm_embedding_provider_on_boot


def test_mcp_agent_tools_use_ainvoke_without_trace() -> None:
    assert "ainvoke_with_workflow_timeout" in inspect.getsource(_invoke_research_article)
    assert "invoke_graph_with_trace" not in inspect.getsource(_invoke_research_article)
    assert "ainvoke_with_workflow_timeout" in inspect.getsource(invoke_content_generation)
    assert "invoke_graph_with_trace" not in inspect.getsource(invoke_content_generation)
    assert "invoke_graph_with_trace" not in inspect.getsource(project_review)


def test_warm_embedding_uses_get_embedding_provider_singleton() -> None:
    source = inspect.getsource(warm_embedding_provider_on_boot)
    assert "get_embedding_provider" in source
    assert "FastEmbedAdapter(" not in source
