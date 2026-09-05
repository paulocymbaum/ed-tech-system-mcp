"""PostgREST adapter for ``update_ai_generation_job`` (service_role only)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import SecretStr

from mcp_server.domain.ai_generation_job import (
    AiGenerationJobProgressPort,
    AiGenerationJobSnapshot,
)
from mcp_server.domain.invariants import require_credential

_RPC_TIMEOUT_SECONDS = 10.0
_UPDATE_ATTEMPTS = 3
_UPDATE_RETRY_SECONDS = 0.2


class SupabaseAiGenerationJobProgress(AiGenerationJobProgressPort):
    """POST /rest/v1/rpc/update_ai_generation_job with service-role headers."""

    def __init__(self, supabase_url: str, service_role_key: SecretStr | str) -> None:
        self._supabase_url = supabase_url.rstrip("/")
        if isinstance(service_role_key, SecretStr):
            self._service_role_key = service_role_key.get_secret_value()
        else:
            self._service_role_key = service_role_key
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=_RPC_TIMEOUT_SECONDS)
        return self._http

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get(self, job_id: str) -> AiGenerationJobSnapshot | None:
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        url = f"{self._supabase_url}/rest/v1/ai_generation_jobs"
        params = {"id": f"eq.{job_id}", "select": "id,status,result_ref"}
        client = await self._client()
        response = await client.get(url, headers=self._headers(), params=params)
        if response.status_code >= 400:
            msg = f"ai_generation_jobs get failed status={response.status_code}"
            raise RuntimeError(msg)
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return None
        row = rows[0]
        if not isinstance(row, dict):
            return None
        status = row.get("status")
        if not isinstance(status, str) or not status:
            return None
        result_ref = row.get("result_ref")
        if result_ref is not None and not isinstance(result_ref, dict):
            result_ref = None
        return AiGenerationJobSnapshot(status=status, result_ref=result_ref)

    async def update(
        self,
        *,
        job_id: str,
        status: str | None = None,
        phase: str | None = None,
        error: str | None = None,
        result_ref: dict[str, Any] | None = None,
    ) -> None:
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        body: dict[str, Any] = {"p_id": job_id}
        if status is not None:
            body["p_status"] = status
        if phase is not None:
            body["p_phase"] = phase
        if error is not None:
            body["p_error"] = error
        if result_ref is not None:
            body["p_result_ref"] = result_ref
        url = f"{self._supabase_url}/rest/v1/rpc/update_ai_generation_job"
        last_error: Exception | None = None
        for attempt in range(1, _UPDATE_ATTEMPTS + 1):
            try:
                client = await self._client()
                response = await client.post(url, headers=self._headers(), json=body)
            except Exception as exc:
                last_error = exc
            else:
                if response.status_code < 400:
                    return
                last_error = RuntimeError(
                    f"update_ai_generation_job failed status={response.status_code}"
                )
            if attempt < _UPDATE_ATTEMPTS:
                await asyncio.sleep(_UPDATE_RETRY_SECONDS)
        if last_error is not None:
            raise last_error
        raise RuntimeError("update_ai_generation_job failed")
