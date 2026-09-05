"""PostgREST adapter for ``patch_tutor_session_draft`` (privileged server only)."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr

from mcp_server.domain.invariants import require_credential
from mcp_server.domain.tutor_session_draft import TutorSessionDraftPort

_RPC_TIMEOUT_SECONDS = 10.0


class SupabaseTutorSessionDraft(TutorSessionDraftPort):
    """POST /rest/v1/rpc/patch_tutor_session_draft with privileged headers."""

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

    async def patch(self, *, session_id: str, draft_reply: str | None) -> None:
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body: dict[str, Any] = {
            "p_session_id": session_id,
            "p_draft_reply": draft_reply,
        }
        url = f"{self._supabase_url}/rest/v1/rpc/patch_tutor_session_draft"
        client = await self._client()
        response = await client.post(url, headers=headers, json=body)
        if response.status_code >= 400:
            msg = f"patch_tutor_session_draft failed status={response.status_code}"
            raise RuntimeError(msg)
