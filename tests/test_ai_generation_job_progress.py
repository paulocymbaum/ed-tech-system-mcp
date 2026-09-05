"""Retries for PostgREST update_ai_generation_job."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from mcp_server.infrastructure.ai_generation_job_progress import SupabaseAiGenerationJobProgress


@pytest.mark.asyncio
async def test_update_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    port = SupabaseAiGenerationJobProgress("http://supabase.example", "service-key")
    calls = {"n": 0}

    class FakeHttp:
        async def post(self, url: str, headers: object = None, json: object = None) -> httpx.Response:
            del headers, json
            calls["n"] += 1
            request = httpx.Request("POST", url)
            if calls["n"] < 3:
                return httpx.Response(503, request=request)
            return httpx.Response(200, json={}, request=request)

    async def fake_client() -> FakeHttp:
        return FakeHttp()

    monkeypatch.setattr(port, "_client", fake_client)
    monkeypatch.setattr(
        "mcp_server.infrastructure.ai_generation_job_progress.asyncio.sleep",
        AsyncMock(),
    )
    await port.update(job_id="job-1", status="running", phase="readme")
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_update_raises_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    port = SupabaseAiGenerationJobProgress("http://supabase.example", "service-key")

    class FakeHttp:
        async def post(self, url: str, headers: object = None, json: object = None) -> httpx.Response:
            del headers, json
            return httpx.Response(500, request=httpx.Request("POST", url))

    async def fake_client() -> FakeHttp:
        return FakeHttp()

    monkeypatch.setattr(port, "_client", fake_client)
    monkeypatch.setattr(
        "mcp_server.infrastructure.ai_generation_job_progress.asyncio.sleep",
        AsyncMock(),
    )
    with pytest.raises(RuntimeError, match="update_ai_generation_job failed"):
        await port.update(job_id="job-1", status="running")
