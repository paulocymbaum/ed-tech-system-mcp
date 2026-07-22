"""Language model registry contract tests."""

import pytest

import mcp_server.application.llm_models as llm_models
from mcp_server.application.llm_models import LanguageModelSpec
from mcp_server.domain.llm_routing import GroqModelRecord


@pytest.fixture(autouse=True)
def _reset_language_model_registry() -> None:
    llm_models.reset_groq_language_models()


def test_l01_available_language_models_is_non_empty() -> None:
    assert len(llm_models.AVAILABLE_LANGUAGE_MODELS) > 0


def test_l02_available_language_models_have_required_fields() -> None:
    required_keys = {"id", "provider", "display_name"}
    for model in llm_models.AVAILABLE_LANGUAGE_MODELS:
        assert required_keys.issubset(model.keys())
        assert model["id"]
        assert model["provider"]
        assert model["display_name"]


def test_l03_available_language_models_include_openai_anthropic_and_groq() -> None:
    llm_models.register_groq_language_models(
        [
            GroqModelRecord(
                model_id="allam-2-7b",
                display_name="Allam 2 7B",
                active=True,
                is_free=True,
                is_developer_plan=False,
                is_routable=True,
            )
        ]
    )
    providers = {model["provider"] for model in llm_models.AVAILABLE_LANGUAGE_MODELS}
    assert "openai" in providers
    assert "anthropic" in providers
    assert "groq" in providers


def test_l04_language_model_spec_typing() -> None:
    sample: LanguageModelSpec = llm_models.AVAILABLE_LANGUAGE_MODELS[0]
    assert isinstance(sample["id"], str)


def test_l05_available_language_models_have_unique_ids() -> None:
    ids = [model["id"] for model in llm_models.AVAILABLE_LANGUAGE_MODELS]
    assert len(ids) == len(set(ids))
