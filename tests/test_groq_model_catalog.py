"""Tests for Groq catalog parsing."""

from mcp_server.infrastructure.groq_model_catalog import catalog_entry_from_api_item


def test_catalog_entry_from_api_item_parses_pricing_and_modalities() -> None:
    entry = catalog_entry_from_api_item(
        {
            "id": "allam-2-7b",
            "owned_by": "SDAIA",
            "name": "Allam 2 7B",
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "pricing": {
                "prompt": "0",
                "completion": "0",
                "request": "0",
                "image": "0",
            },
        }
    )
    assert entry is not None
    assert entry.model_id == "allam-2-7b"
    assert entry.display_name == "Allam 2 7B"
    assert entry.pricing is not None
    assert entry.pricing.prompt == 0.0
    assert entry.input_modalities == ("text",)


def test_catalog_entry_from_api_item_returns_none_without_id() -> None:
    assert catalog_entry_from_api_item({"name": "orphan"}) is None
