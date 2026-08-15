"""Graph node search for lesson authoring grounding (E6.2)."""

from __future__ import annotations

from pydantic import SecretStr
from supabase import Client, create_client

from mcp_server.domain.authoring import GraphNodeHit, GraphSearchPort
from mcp_server.domain.invariants import require_credential


class GraphSearchRepository(GraphSearchPort):
    """Resolve curriculum topics via ``search_graph_nodes`` (service role read)."""

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

    def search_graph_nodes(
        self,
        *,
        tenant_id: str,
        query: str,
        course_slug: str | None = None,
        min_similarity: float = 0.1,
        limit: int = 5,
    ) -> list[GraphNodeHit]:
        q = query.strip()
        if not q:
            return []
        params: dict[str, object] = {
            "p_tenant_id": tenant_id,
            "p_query": q[:200],
            "p_min_similarity": min_similarity,
            "p_limit": limit,
        }
        if course_slug:
            params["p_course_slug"] = course_slug
        try:
            raw = self._client_or_create().rpc("search_graph_nodes", params).execute().data
        except Exception:  # noqa: BLE001
            return []
        rows = raw if isinstance(raw, list) else []
        hits: list[GraphNodeHit] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            node_id = row.get("node_id")
            label = row.get("label") or row.get("node_label")
            if not node_id or not label:
                continue
            score_raw = row.get("score") or row.get("similarity")
            min_raw = row.get("min_word_score")
            hits.append(
                GraphNodeHit(
                    node_id=str(node_id),
                    label=str(label),
                    graph_index=str(row["graph_index"]) if row.get("graph_index") else None,
                    course_slug=str(row["course_slug"]) if row.get("course_slug") else None,
                    course_title=str(row["course_title"]) if row.get("course_title") else None,
                    kind=str(row["kind"]) if row.get("kind") else None,
                    score=float(score_raw) if isinstance(score_raw, (int, float)) else None,
                    min_word_score=float(min_raw) if isinstance(min_raw, (int, float)) else None,
                )
            )
        return hits
