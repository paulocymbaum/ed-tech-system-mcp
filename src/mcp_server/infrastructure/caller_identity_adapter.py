"""Verify caller JWTs via Supabase Auth; check tenant_memberships with service role."""

from __future__ import annotations

import httpx
from pydantic import SecretStr
from supabase import Client, create_client

from mcp_server.domain.exceptions import DomainAuthorizationError
from mcp_server.domain.invariants import require_credential

_AUTH_TIMEOUT_SECONDS = 8.0


class SupabaseCallerIdentityAdapter:
    """Infrastructure adapter for MCP privileged-tool auth."""

    def __init__(self, supabase_url: str, service_role_key: SecretStr | str) -> None:
        self._supabase_url = supabase_url.rstrip("/")
        if isinstance(service_role_key, SecretStr):
            self._service_role_key = service_role_key.get_secret_value()
        else:
            self._service_role_key = service_role_key
        self._client: Client | None = None

    def _client_or_create(self) -> Client:
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        if self._client is None:
            self._client = create_client(self._supabase_url, self._service_role_key)
        return self._client

    def user_id_from_jwt(self, caller_jwt: str) -> str:
        token = caller_jwt.removeprefix("Bearer ").strip()
        if not token:
            raise DomainAuthorizationError("Caller JWT is required")
        require_credential(self._supabase_url, resource="Supabase")
        require_credential(self._service_role_key, resource="Supabase")
        url = f"{self._supabase_url}/auth/v1/user"
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {token}",
        }
        try:
            with httpx.Client(timeout=_AUTH_TIMEOUT_SECONDS) as client:
                response = client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise DomainAuthorizationError("Could not verify caller") from exc
        if response.status_code >= 400:
            raise DomainAuthorizationError("Could not verify caller")
        payload = response.json()
        user_id = payload.get("id") if isinstance(payload, dict) else None
        if not isinstance(user_id, str) or not user_id.strip():
            raise DomainAuthorizationError("Could not verify caller")
        return user_id.strip()

    def is_tenant_member(self, *, user_id: str, tenant_id: str) -> bool:
        client = self._client_or_create()
        result = (
            client.table("tenant_memberships")
            .select("user_id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = result.data if isinstance(result.data, list) else []
        return len(rows) > 0
