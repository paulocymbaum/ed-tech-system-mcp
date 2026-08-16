"""Tavily web search adapter."""

from __future__ import annotations

import httpx

from mcp_server.domain.interfaces import ISearchClient
from mcp_server.domain.invariants import (
    require_credential,
    require_non_empty_text,
    require_positive_int,
)


class TavilySearchClient(ISearchClient):
    """Adapter for Tavily search API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    async def search(self, query: str, max_results: int = 5) -> list[str]:
        query = require_non_empty_text(query, field="query")
        max_results = require_positive_int(max_results, field="max_results")
        require_credential(self._api_key, resource="Tavily API")

        client = await self._client()
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self._api_key,
                "query": query,
                "max_results": max_results,
            },
        )
        response.raise_for_status()
        payload = response.json()

        results: list[str] = []
        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            content = str(item.get("content", "")).strip()
            url = str(item.get("url", "")).strip()
            snippet = " — ".join(part for part in (title, content, url) if part)
            if snippet:
                results.append(snippet)
            if len(results) >= max_results:
                break
        return results
