"""Bundled corpus fixture for RAG validation in the local workflow UI."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE_DOCUMENT_ID = "00000000-0000-4000-8000-000000000001"
FIXTURE_TITLE = "RAG Validation Fixture — Photosynthesis"
DEFAULT_QUERY = "How does photosynthesis convert light energy?"
DEFAULT_EXPECTED_PHRASES = ("chlorophyll", "light-dependent reactions", "glucose")

_REPO_ROOT = Path(__file__).resolve().parents[5]
FIXTURE_DIR = _REPO_ROOT / "fixtures" / "rag_validation"
DEFAULT_CORPUS_PATH = FIXTURE_DIR / "corpus.md"
EXPECTED_PHRASES_PATH = FIXTURE_DIR / "expected_phrases.json"


def resolve_fixture_path(path: str | None = None) -> Path:
    """Return the corpus file path, defaulting to the bundled fixture."""
    if path is None or not path.strip():
        return DEFAULT_CORPUS_PATH
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = _REPO_ROOT / candidate
    return candidate


def load_default_document_text() -> str:
    """Return the bundled validation corpus markdown."""
    return DEFAULT_CORPUS_PATH.read_text(encoding="utf-8")


def default_document_defaults() -> dict[str, object]:
    """Defaults for the local UI document editor."""
    return {
        "document_title": FIXTURE_TITLE,
        "document_text": load_default_document_text(),
        "query": DEFAULT_QUERY,
        "expected_phrases": load_expected_phrases(),
    }


def resolve_document_text(
    state_text: str | None,
    *,
    fixture_path: str | None = None,
) -> tuple[str, str]:
    """Return document body and source label from inline text or fixture file."""
    if state_text is not None and state_text.strip():
        return state_text, "inline"
    path = resolve_fixture_path(fixture_path)
    if not path.is_file():
        msg = f"RAG validation fixture not found: {path}"
        raise FileNotFoundError(msg)
    return path.read_text(encoding="utf-8"), str(path)


def load_expected_phrases(custom: list[str] | None = None) -> list[str]:
    """Load expected retrieval phrases from request override or bundled JSON."""
    if custom:
        return [phrase.strip() for phrase in custom if phrase.strip()]
    if EXPECTED_PHRASES_PATH.is_file():
        payload = json.loads(EXPECTED_PHRASES_PATH.read_text(encoding="utf-8"))
        phrases = payload.get("phrases", [])
        if isinstance(phrases, list):
            return [str(item).strip() for item in phrases if str(item).strip()]
    return list(DEFAULT_EXPECTED_PHRASES)
