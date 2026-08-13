"""Supabase-backed project review context + grade persist (E7)."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import SecretStr
from supabase import Client, create_client

from mcp_server.domain.invariants import require_credential
from mcp_server.domain.project_review import (
    ProjectReviewContext,
    ProjectReviewDelivery,
    ProjectReviewFile,
    ProjectReviewGrade,
    ProjectReviewResult,
)


class ProjectReviewRepository:
    """Collect review context and persist grades via public RPCs / EF7."""

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

    def collect_context(
        self,
        *,
        tenant_id: str,
        course_slug: str,
        module_slug: str,
        lesson_slug: str,
        project_slug: str,
        user_id: str,
        delivery_limit: int = 3,
    ) -> ProjectReviewContext:
        client = self._client_or_create()

        project_id = client.rpc(
            "project_id_by_slugs",
            {
                "p_tenant_id": tenant_id,
                "p_course_slug": course_slug,
                "p_module_slug": module_slug,
                "p_lesson_slug": lesson_slug,
                "p_project_slug": project_slug,
            },
        ).execute().data
        if not project_id:
            raise ValueError("Project not found")

        catalog = client.rpc(
            "get_course_catalog",
            {"p_tenant_id": tenant_id, "p_course_slug": course_slug},
        ).execute().data
        project_blob = _find_project(catalog, project_slug, module_slug, lesson_slug)
        readme = str(project_blob.get("readmeMarkdown") or "")
        starter_files = _starter_files_from_entries(project_blob.get("entries") or [])
        lesson_markdown = _lesson_markdown(catalog, module_slug, lesson_slug)

        raw_deliveries = client.rpc(
            "list_project_deliveries",
            {
                "p_project_id": project_id,
                "p_user_id": user_id,
                "p_limit": delivery_limit,
            },
        ).execute().data
        deliveries = _parse_deliveries(raw_deliveries)
        latest_id = deliveries[-1].id if deliveries else None

        return ProjectReviewContext(
            tenant_id=tenant_id,
            course_slug=course_slug,
            module_slug=module_slug,
            lesson_slug=lesson_slug,
            project_slug=project_slug,
            project_id=str(project_id),
            user_id=user_id,
            readme_markdown=readme,
            lesson_markdown=lesson_markdown,
            starter_files=starter_files,
            deliveries=deliveries,
            latest_delivery_id=latest_id,
        )

    def persist_grade(
        self,
        *,
        delivery_id: str,
        grade: ProjectReviewGrade,
    ) -> ProjectReviewResult:
        """POST EF7 with service role (RPC allows service_role after E7 migration)."""
        url = f"{self._supabase_url}/functions/v1/grade-project-delivery"
        headers = {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "delivery_id": delivery_id,
            "score": grade.score,
            "comment": grade.comment,
        }
        with httpx.Client(timeout=30.0) as http:
            response = http.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        data = body.get("data") if isinstance(body, dict) else body
        data = data if isinstance(data, dict) else {}
        return ProjectReviewResult(
            score=grade.score,
            comment=grade.comment,
            passed=bool(data.get("passed", grade.score > 80)),
            delivery_id=delivery_id,
            persisted=True,
            progress_updated=bool(data.get("progress_updated", False)),
            review_id=str(data["review_id"]) if data.get("review_id") else None,
        )


def _find_project(
    catalog: object,
    project_slug: str,
    module_slug: str,
    lesson_slug: str,
) -> dict[str, Any]:
    if not isinstance(catalog, dict):
        return {}
    projects = catalog.get("projects")
    if not isinstance(projects, list):
        return {}
    for item in projects:
        if not isinstance(item, dict):
            continue
        if str(item.get("id")) != project_slug:
            continue
        if module_slug and str(item.get("moduleId") or "") not in ("", module_slug):
            continue
        if lesson_slug and str(item.get("lessonId") or "") not in ("", lesson_slug):
            continue
        return item
    return {}


def _lesson_markdown(catalog: object, module_slug: str, lesson_slug: str) -> str:
    if not isinstance(catalog, dict):
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


def _starter_files_from_entries(entries: object) -> list[ProjectReviewFile]:
    if not isinstance(entries, list):
        return []
    files: list[ProjectReviewFile] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or "")
        if entry.get("kind") != "file":
            continue
        if not path.startswith("starter/"):
            continue
        if path.endswith("tests.json") or path.endswith("sample.input"):
            continue
        content = entry.get("content")
        if isinstance(content, str) and content.strip():
            files.append(ProjectReviewFile(path=path, content=content))
    return files


def _parse_deliveries(raw: object) -> list[ProjectReviewDelivery]:
    if not isinstance(raw, list):
        return []
    out: list[ProjectReviewDelivery] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        delivery_id = item.get("id")
        content = item.get("content")
        submitted = item.get("submitted_at")
        if not isinstance(delivery_id, str) or not isinstance(content, str):
            continue
        out.append(
            ProjectReviewDelivery(
                id=delivery_id,
                content=content,
                submitted_at=str(submitted or ""),
                review=item.get("review") if isinstance(item.get("review"), dict) else None,
            )
        )
    return out
