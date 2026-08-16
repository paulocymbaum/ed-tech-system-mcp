"""E18.4: grader LLM failures must not look like a scored review."""

import pytest

from mcp_server.application.agents.project_review.graph import result_from_state
from mcp_server.domain.exceptions import ExternalServiceError


def test_llm_failed_state_raises_unavailable() -> None:
    state = {
        "tenant_id": "t",
        "course_slug": "c",
        "module_slug": "m",
        "lesson_slug": "l",
        "project_slug": "p",
        "user_id": "u",
        "delivery_limit": 3,
        "persist": False,
        "context": None,
        "score": None,
        "comment": None,
        "result": None,
        "error": "llm_failed:timeout",
    }
    with pytest.raises(ExternalServiceError, match="temporarily unavailable"):
        result_from_state(state)  # type: ignore[arg-type]
