"""Load RAG validation benchmark scenarios from JSON fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from mcp_server.application.agents.rag_validation.fixture import (
    DEFAULT_QUERY,
    FIXTURE_DIR,
    load_default_document_text,
    load_expected_phrases,
    resolve_repo_root,
)

DEFAULT_SCENARIOS_PATH = FIXTURE_DIR / "search_scenarios.json"


@dataclass(frozen=True, slots=True)
class RagSearchScenario:
    """One query + expected phrases used to score a hyperparameter configuration."""

    name: str
    query: str
    expected_phrases: tuple[str, ...]
    document_text: str | None = None
    fixture_path: str | None = None
    document_title: str | None = None
    gold_answer: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "query": self.query,
            "expected_phrases": list(self.expected_phrases),
            "document_text": self.document_text,
            "fixture_path": self.fixture_path,
            "document_title": self.document_title,
            "gold_answer": self.gold_answer,
        }


def resolve_scenarios_path(path: str | Path | None = None) -> Path:
    if path is None:
        return DEFAULT_SCENARIOS_PATH
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolve_repo_root() / candidate
    return candidate


def load_search_scenarios(path: str | Path | None = None) -> list[RagSearchScenario]:
    """Load benchmark scenarios from JSON, falling back to bundled defaults."""
    scenarios_path = resolve_scenarios_path(path)
    if scenarios_path.is_file():
        payload = json.loads(scenarios_path.read_text(encoding="utf-8"))
        raw_scenarios = payload.get("scenarios", [])
        if isinstance(raw_scenarios, list) and raw_scenarios:
            return [_scenario_from_dict(item) for item in raw_scenarios]
    return [_default_scenario()]


def _default_scenario() -> RagSearchScenario:
    return RagSearchScenario(
        name="default",
        query=DEFAULT_QUERY,
        expected_phrases=tuple(load_expected_phrases()),
        document_text=load_default_document_text(),
    )


def _scenario_from_dict(payload: object) -> RagSearchScenario:
    if not isinstance(payload, dict):
        msg = "Each scenario must be a JSON object"
        raise ValueError(msg)
    name = str(payload.get("name", "scenario")).strip() or "scenario"
    query = str(payload.get("query", DEFAULT_QUERY)).strip() or DEFAULT_QUERY
    phrases_raw = payload.get("expected_phrases")
    if isinstance(phrases_raw, list) and phrases_raw:
        expected_phrases = tuple(str(item).strip() for item in phrases_raw if str(item).strip())
    else:
        expected_phrases = tuple(load_expected_phrases())
    document_text = payload.get("document_text")
    fixture_path = payload.get("fixture_path")
    document_title = payload.get("document_title")
    return RagSearchScenario(
        name=name,
        query=query,
        expected_phrases=expected_phrases,
        document_text=str(document_text) if isinstance(document_text, str) else None,
        fixture_path=str(fixture_path) if isinstance(fixture_path, str) else None,
        document_title=str(document_title) if isinstance(document_title, str) else None,
    )
