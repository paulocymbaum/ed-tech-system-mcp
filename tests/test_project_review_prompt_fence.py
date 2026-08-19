from mcp_server.application.agents.project_review.prompts import grade_user_prompt
from mcp_server.domain.project_review import ProjectReviewContext, ProjectReviewDelivery


def test_grade_user_prompt_fences_learner_deliveries() -> None:
    context = ProjectReviewContext(
        tenant_id="tenant",
        course_slug="course",
        module_slug="module",
        lesson_slug="lesson",
        project_slug="project",
        project_id="project-id",
        user_id="user-id",
        deliveries=[
            ProjectReviewDelivery(
                id="d1",
                content="print('hello')",
                submitted_at="2026-01-01T00:00:00Z",
            )
        ],
    )
    prompt = grade_user_prompt(context)
    assert "<delivery_1>" in prompt
    assert "<latest_delivery>" in prompt
    assert "untrusted user data" in prompt
