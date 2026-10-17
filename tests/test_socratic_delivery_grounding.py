"""BL-147: the learner's delivery editor code reaches the tutor prompt fenced."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_server.application.agents.socratic.prompts import socratic_user_prompt
from mcp_server.interface.custom_tools_socratic import SocraticTutorRequest


def _prompt(delivery_draft: str | None) -> str:
    return socratic_user_prompt(
        message="Where do I handle errors?",
        history=[],
        grounding=None,
        learner_delivery_draft=delivery_draft,
        course_slug="javascript",
        module_slug=None,
        lesson_slug="01.2.1-promises",
        project_slug="async-pipeline",
    )


def test_delivery_draft_is_fenced_in_prompt() -> None:
    prompt = _prompt("fetch(url).then((r) => r.json())")
    assert "Learner's current delivery code" in prompt
    assert "learner_code" in prompt
    assert "fetch(url).then((r) => r.json())" in prompt


def test_delivery_draft_absent_omits_section() -> None:
    assert "Learner's current delivery code" not in _prompt(None)


def test_delivery_draft_is_capped_before_prompt() -> None:
    prompt = _prompt("x" * 5000)
    # The draft is capped (3000 chars) before the safety wrapper.
    assert prompt.count("x") < 5000


def test_request_model_caps_delivery_draft() -> None:
    with pytest.raises(ValidationError):
        SocraticTutorRequest(
            tenant_id="t",
            course_slug="course",
            message="hello",
            learner_delivery_draft="x" * 12001,
        )
