"""Tests for public MCP tools in custom_tools.py."""

from __future__ import annotations

import pytest

from mcp_server.domain.interfaces import ISearchClient
from mcp_server.interface.custom_tools import _invoke_search_web
from mcp_server.interface.validation import WebSearchRequest


class FakeSearchClient(ISearchClient):
    async def search(self, query: str, max_results: int = 5) -> list[str]:
        return [f"result for {query}"][:max_results]


@pytest.mark.asyncio
async def test_invoke_search_web(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_server.application.search_services.get_search_client",
        lambda: FakeSearchClient(),
    )

    response = await _invoke_search_web(
        WebSearchRequest(query="photosynthesis", max_results=3),
    )

    assert response.results == ["result for photosynthesis"]
