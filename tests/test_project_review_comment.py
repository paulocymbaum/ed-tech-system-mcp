"""Unit tests for project review comment validation (E7)."""

from mcp_server.domain.project_review import validate_review_comment


def test_comment_ok_short_plain() -> None:
    result = validate_review_comment(
        "Reads stdin correctly. Age uses Number.isFinite. Next: normalize isActive casing."
    )
    assert result["ok"] is True


def test_comment_rejects_banned_delivery_tab() -> None:
    result = validate_review_comment(
        "Looks good but the Delivery tab sync failed. Next: resubmit."
    )
    assert result["ok"] is False


def test_comment_rejects_too_long() -> None:
    result = validate_review_comment("x" * 500)
    assert result["ok"] is False
