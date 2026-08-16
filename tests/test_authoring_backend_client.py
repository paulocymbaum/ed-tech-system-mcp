"""Tests for authoring backend RPC client (E6.1) — mocked HTTP."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mcp_server.application.authoring_service import (
    AuthoringService,
    harness_quiz_to_rpc_payload,
)
from mcp_server.infrastructure.authoring_backend_client import AuthoringBackendClient


@pytest.mark.asyncio
async def test_save_lesson_bundle_calls_rpc_sequence() -> None:
    client = AuthoringBackendClient("https://example.supabase.co", "jwt-token")
    calls: list[tuple[str, dict]] = []

    async def fake_post(name: str, body: dict) -> object:
        calls.append((name, body))
        if name == "upsert_lesson":
            return "lesson-uuid"
        if name == "upsert_lesson_content_document":
            return "doc-uuid"
        if name == "upsert_quiz_tree":
            return "quiz-uuid"
        return {}

    with patch.object(client, "_post_rpc", side_effect=fake_post):
        service = AuthoringService(client)
        result = await service.save_lesson_bundle(
            module_id="00000000-0000-4000-8000-000000000001",
            lesson_slug="01.1-lesson",
            lesson={
                "readme_markdown": "# Lesson\n\nContent body for the lesson.",
                "meta": {
                    "id": "01.1-lesson",
                    "graphIndex": "01.1",
                    "graphNodeId": "00000000-0000-4000-8000-000000000099",
                    "title": "Lesson",
                },
            },
            quiz={
                "id": "quiz",
                "title": "Quiz",
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "Q?",
                        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                        "correctOptionId": "a",
                    }
                ],
            },
        )

    assert result.lesson_id == "lesson-uuid"
    assert result.quiz_id == "quiz-uuid"
    rpc_names = [name for name, _ in calls]
    assert rpc_names == ["upsert_lesson", "upsert_lesson_content_document", "upsert_quiz_tree"]


def test_harness_quiz_to_rpc_maps_option_slugs() -> None:
    payload = harness_quiz_to_rpc_payload(
        {
            "id": "quiz",
            "title": "T",
            "questions": [
                {
                    "id": "q1",
                    "prompt": "P",
                    "correctOptionId": "b",
                    "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
                }
            ],
        }
    )
    assert payload["questions"][0]["correct_option_slug"] == "b"
    assert payload["questions"][0]["options"][0]["slug"] == "a"
