"""PostgREST RPC client for curriculum authoring with manager JWT (E6.1)."""

from __future__ import annotations

from typing import Any

import httpx

from mcp_server.domain.authoring import AuthoringBackendFactoryPort, AuthoringBackendPort
from mcp_server.domain.exceptions import DomainValidationError, ResourceNotFoundError


class AuthoringBackendClient(AuthoringBackendPort):
    """Call public ``upsert_*`` / ``publish_lesson`` RPCs with a manager user JWT."""

    def __init__(
        self,
        supabase_url: str,
        manager_jwt: str,
        *,
        anon_key: str | None = None,
    ) -> None:
        base = supabase_url.rstrip("/")
        self._rpc_base = f"{base}/rest/v1/rpc"
        self._manager_jwt = manager_jwt.strip()
        if not self._manager_jwt:
            msg = "manager_jwt is required for authoring RPCs (manager+ role)"
            raise DomainValidationError(msg)
        # PostgREST/Kong requires the project anon (or service_role) key in
        # ``apikey``. A user JWT is valid for Authorization only — using it as
        # apikey yields HTTP 401 "Invalid API key".
        apikey = (anon_key or "").strip()
        if not apikey:
            msg = (
                "SUPABASE_ANON_KEY (or VITE_SUPABASE_ANON_KEY) is required "
                "for authoring RPCs; user JWT cannot be used as apikey"
            )
            raise DomainValidationError(msg)
        self._headers = {
            "Authorization": f"Bearer {self._manager_jwt}",
            "apikey": apikey,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=60.0)
        return self._http

    async def _post_rpc(self, name: str, body: dict[str, Any]) -> Any:
        client = await self._client()
        response = await client.post(
            f"{self._rpc_base}/{name}",
            headers=self._headers,
            json=body,
        )
        if response.status_code >= 400:
            detail = response.text[:500]
            msg = f"RPC {name} failed ({response.status_code}): {detail}"
            raise DomainValidationError(msg)
        if not response.content:
            return None
        return response.json()

    async def upsert_lesson(
        self,
        *,
        module_id: str,
        slug: str,
        title: str,
        description: str | None = None,
        graph_index: str | None = None,
        graph_node_id: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "p_module_id": module_id,
            "p_slug": slug,
            "p_title": title,
            "p_status": "draft",
        }
        if description is not None:
            payload["p_description"] = description
        if graph_index is not None:
            payload["p_graph_index"] = graph_index
        if graph_node_id is not None:
            payload["p_graph_node_id"] = graph_node_id
        result = await self._post_rpc("upsert_lesson", payload)
        return str(result)

    async def upsert_lesson_content_document(
        self,
        *,
        lesson_id: str,
        readme_markdown: str,
        source_path: str,
    ) -> str:
        result = await self._post_rpc(
            "upsert_lesson_content_document",
            {
                "p_lesson_id": lesson_id,
                "p_readme_markdown": readme_markdown,
                "p_source_path": source_path,
            },
        )
        return str(result)

    async def upsert_quiz_tree(self, *, lesson_id: str, quiz: dict[str, Any]) -> str:
        result = await self._post_rpc(
            "upsert_quiz_tree",
            {"p_lesson_id": lesson_id, "p_quiz": quiz},
        )
        return str(result)

    async def upsert_project_tree(self, *, lesson_id: str, project: dict[str, Any]) -> str:
        result = await self._post_rpc(
            "upsert_project_tree",
            {"p_lesson_id": lesson_id, "p_project": project},
        )
        return str(result)

    async def set_lesson_stack_runtime(
        self,
        *,
        lesson_id: str,
        stack: str,
        test_boilerplate_id: str | None = None,
        boilerplate_slug: str | None = None,
        run_config: dict[str, Any] | None = None,
        dependencies: list[dict[str, Any]] | None = None,
        project_id: str | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "p_lesson_id": lesson_id,
            "p_stack": stack,
            "p_run_config": run_config or {},
            "p_dependencies": dependencies or [],
        }
        if test_boilerplate_id:
            payload["p_test_boilerplate_id"] = test_boilerplate_id
        if boilerplate_slug:
            payload["p_boilerplate_slug"] = boilerplate_slug
        if project_id:
            payload["p_project_id"] = project_id
        result = await self._post_rpc("set_lesson_stack_runtime", payload)
        return str(result)

    async def publish_lesson(self, *, lesson_id: str) -> dict[str, Any]:
        result = await self._post_rpc("publish_lesson", {"p_lesson_id": lesson_id})
        if isinstance(result, dict):
            return result
        return {"lesson_id": lesson_id}


class AuthoringBackendClientFactory(AuthoringBackendFactoryPort):
    """Build per-request clients when JWT is supplied by the MCP tool caller."""

    def __init__(self, supabase_url: str, *, anon_key: str | None = None) -> None:
        if not supabase_url.strip():
            raise ResourceNotFoundError("SUPABASE_URL is not configured")
        self._supabase_url = supabase_url
        self._anon_key = anon_key

    def for_jwt(self, manager_jwt: str) -> AuthoringBackendClient:
        return AuthoringBackendClient(
            self._supabase_url,
            manager_jwt,
            anon_key=self._anon_key,
        )
