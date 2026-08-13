"""Unit tests for socratic tutor reply validation (E8)."""

from mcp_server.domain.socratic import normalize_locale, validate_socratic_reply


def test_normalize_locale_defaults_en() -> None:
    assert normalize_locale(None) == "en"
    assert normalize_locale("pt-BR") == "pt"
    assert normalize_locale("zz") == "en"


def test_reply_rejects_score_language() -> None:
    result = validate_socratic_reply("Nice work. Score: 90 out of 100.")
    assert result["ok"] is False


def test_reply_ok_with_question() -> None:
    result = validate_socratic_reply(
        "You're close on truthiness.\nWhat happens if you check Boolean([])?\n"
        "Try predicting before running it."
    )
    assert result["ok"] is True
