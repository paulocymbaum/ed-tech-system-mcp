"""Supabase catalog + graph grounding for socratic tutor (E8)."""

from __future__ import annotations

from pydantic import SecretStr
from supabase import Client, create_client

from mcp_server.domain.invariants import require_credential
from mcp_server.domain.socratic import (
    SocraticCatalogPort,
    SocraticGraphHit,
    SocraticGrounding,
)


class SocraticCatalogRepository(SocraticCatalogPort):
    """Load lesson/project snippets and search_graph_nodes hits."""

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

    def load_grounding(
        self,
        *,
        tenant_id: str,
        course_slug: str,
        module_slug: str | None,
        lesson_slug: str | None,
        project_slug: str | None,
        query: str,
    ) -> SocraticGrounding:
        client = self._client_or_create()
        catalog = (
            client.rpc(
                "get_course_catalog",
                {"p_tenant_id": tenant_id, "p_course_slug": course_slug},
            )
            .execute()
            .data
        )
        lesson_markdown = _lesson_markdown(catalog, module_slug, lesson_slug)
        project_readme = _project_readme(catalog, project_slug, module_slug, lesson_slug)
        graph_hits = _search_graph(client, tenant_id, course_slug, query)
        return SocraticGrounding(
            lesson_markdown=lesson_markdown,
            project_readme=project_readme,
            graph_hits=graph_hits,
            documents=[],
        )


def _lesson_markdown(
    catalog: object, module_slug: str | None, lesson_slug: str | None
) -> str:
    if not isinstance(catalog, dict) or not module_slug or not lesson_slug:
        return ""
    modules = catalog.get("modules")
    if not isinstance(modules, list):
        return ""
    for module in modules:
        if not isinstance(module, dict) or str(module.get("id")) != module_slug:
            continue
        lessons = module.get("lessons")
        if not isinstance(lessons, list):
            return ""
        for lesson in lessons:
            if isinstance(lesson, dict) and str(lesson.get("id")) == lesson_slug:
                return str(lesson.get("markdown") or "")
    return ""


def _project_readme(
    catalog: object,
    project_slug: str | None,
    module_slug: str | None,
    lesson_slug: str | None,
) -> str:
    if not isinstance(catalog, dict) or not project_slug:
        return ""
    projects = catalog.get("projects")
    if not isinstance(projects, list):
        return ""
    for item in projects:
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) != project_slug:
            continue
        if module_slug and str(item.get("moduleId") or "") not in ("", module_slug):
            continue
        if lesson_slug and str(item.get("lessonId") or "") not in ("", lesson_slug):
            continue
        return str(item.get("readmeMarkdown") or "")
    return ""


def _search_graph(
    client: Client, tenant_id: str, course_slug: str, query: str
) -> list[SocraticGraphHit]:
    q = query.strip()
    if not q:
        return []
    try:
        raw = (
            client.rpc(
                "search_graph_nodes",
                {
                    "p_tenant_id": tenant_id,
                    "p_query": q[:200],
                    "p_course_slug": course_slug,
                    "p_min_similarity": 0.1,
                    "p_limit": 5,
                },
            )
            .execute()
            .data
        )
    except Exception:  # noqa: BLE001
        return []
    hits: list[SocraticGraphHit] = []
    rows = raw if isinstance(raw, list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or row.get("node_label") or "")
        if not label:
            continue
        path = row.get("path") or row.get("node_path")
        score_raw = row.get("score") or row.get("similarity")
        score = float(score_raw) if isinstance(score_raw, (int, float)) else None
        hits.append(
            SocraticGraphHit(
                label=label,
                path=str(path) if path else None,
                score=score,
            )
        )
    return hits
