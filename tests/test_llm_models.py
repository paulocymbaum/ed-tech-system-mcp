"""Language model registry contract tests."""

from mcp_server.application.llm_models import AVAILABLE_LANGUAGE_MODELS, LanguageModelSpec


def test_l01_available_language_models_is_non_empty() -> None:
    assert len(AVAILABLE_LANGUAGE_MODELS) > 0


def test_l02_available_language_models_have_required_fields() -> None:
    required_keys = {"id", "provider", "display_name"}
    for model in AVAILABLE_LANGUAGE_MODELS:
        assert required_keys.issubset(model.keys())
        assert model["id"]
        assert model["provider"]
        assert model["display_name"]


def test_l03_available_language_models_include_openai_anthropic_and_groq() -> None:
    providers = {model["provider"] for model in AVAILABLE_LANGUAGE_MODELS}
    assert "openai" in providers
    assert "anthropic" in providers
    assert "groq" in providers


def test_l04_language_model_spec_typing() -> None:
    sample: LanguageModelSpec = AVAILABLE_LANGUAGE_MODELS[0]
    assert isinstance(sample["id"], str)


def test_l05_available_language_models_have_unique_ids() -> None:
    ids = [model["id"] for model in AVAILABLE_LANGUAGE_MODELS]
    assert len(ids) == len(set(ids))
