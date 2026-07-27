"""Bundled corpus fixture for RAG validation in the local workflow UI."""

from __future__ import annotations

import json
from pathlib import Path

from mcp_server.domain.rag_hyperparameters import OptimizedRagHyperparameters

FIXTURE_DOCUMENT_ID = "00000000-0000-4000-8000-000000000001"
FIXTURE_TITLE = "RAG Validation Fixture — Photosynthesis"
DEFAULT_QUERY = "How does photosynthesis convert light energy?"
DEFAULT_EXPECTED_PHRASES = ("chlorophyll", "light-dependent reactions", "glucose")


def resolve_repo_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parents[5]


FIXTURE_DIR = resolve_repo_root() / "fixtures" / "rag_validation"
DEFAULT_CORPUS_PATH = FIXTURE_DIR / "corpus.md"
EXPECTED_PHRASES_PATH = FIXTURE_DIR / "expected_phrases.json"
OPTIMIZED_HYPERPARAMETERS_PATH = FIXTURE_DIR / "optimized_hyperparameters.json"
OPTIMIZATION_REPORT_PATH = FIXTURE_DIR / "optimization_report.json"


def resolve_fixture_path(path: str | None = None) -> Path:
    """Return the corpus file path, defaulting to the bundled fixture."""
    if path is None or not path.strip():
        return DEFAULT_CORPUS_PATH
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolve_repo_root() / candidate
    return candidate


def load_default_document_text() -> str:
    """Return the bundled validation corpus markdown."""
    return DEFAULT_CORPUS_PATH.read_text(encoding="utf-8")


def default_document_defaults() -> dict[str, object]:
    """Defaults for the local UI document editor."""
    defaults: dict[str, object] = {
        "document_title": FIXTURE_TITLE,
        "document_text": load_default_document_text(),
        "query": DEFAULT_QUERY,
        "expected_phrases": load_expected_phrases(),
    }
    optimized = load_optimized_hyperparameters()
    if optimized is not None:
        defaults["suggested_hyperparameters"] = optimized.hyperparameters.as_dict()
    return defaults


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


def resolve_optimized_hyperparameters_path(path: str | Path | None = None) -> Path:
    """Return the optimized hyperparameters JSON path."""
    if path is None:
        return OPTIMIZED_HYPERPARAMETERS_PATH
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolve_repo_root() / candidate
    return candidate


def load_optimized_hyperparameters(
    path: str | Path | None = None,
) -> OptimizedRagHyperparameters | None:
    """Load persisted optimized hyperparameters, or None when the file is absent."""
    target = resolve_optimized_hyperparameters_path(path)
    if not target.is_file():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Optimized hyperparameters file must contain a JSON object: {target}"
        raise ValueError(msg)
    return OptimizedRagHyperparameters.from_dict(payload)


def save_optimized_hyperparameters(
    result: OptimizedRagHyperparameters,
    path: str | Path | None = None,
) -> Path:
    """Persist optimized hyperparameters to the bundled fixture path by default."""
    target = resolve_optimized_hyperparameters_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(result.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target
