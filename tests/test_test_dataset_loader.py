"""Tests for test-dataset CSV scenario loading."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from mcp_server.application.agents.rag_validation.test_dataset_loader import (
    TestDatasetNotFoundError,
    load_test_dataset_scenarios,
    summarize_test_dataset,
    test_dataset_is_available,
)

test_dataset_is_available.__test__ = False  # noqa: SLF001 — avoid pytest collection


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _bootstrap_dataset(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    _write_csv(
        data_dir / "scenarios.csv",
        [
            "scenario_id",
            "query_id",
            "domain",
            "primary_doc_id",
            "query",
            "gold_answer",
            "scenario_type",
            "has_answer_in_corpus",
            "n_eval_examples",
            "is_used_in_eval",
            "split",
            "difficulty_level",
            "use_case",
        ],
        [
            {
                "scenario_id": "SC0001",
                "query_id": "Q0001",
                "domain": "developer_docs",
                "primary_doc_id": "DOC0001",
                "query": "How do I authenticate?",
                "gold_answer": "API keys are passed as a bearer token.",
                "scenario_type": "standard_qa",
                "has_answer_in_corpus": "1",
                "n_eval_examples": "1",
                "is_used_in_eval": "1",
                "split": "train",
                "difficulty_level": "easy",
                "use_case": "rag_evaluation",
            },
            {
                "scenario_id": "SC0002",
                "query_id": "Q0002",
                "domain": "developer_docs",
                "primary_doc_id": "DOC0002",
                "query": "Missing answer probe",
                "gold_answer": "NO_ANSWER_IN_CORPUS",
                "scenario_type": "no_answer_probe",
                "has_answer_in_corpus": "0",
                "n_eval_examples": "1",
                "is_used_in_eval": "1",
                "split": "train",
                "difficulty_level": "easy",
                "use_case": "rag_evaluation",
            },
            {
                "scenario_id": "SC0003",
                "query_id": "Q0003",
                "domain": "developer_docs",
                "primary_doc_id": "DOC0001",
                "query": "Unused scenario",
                "gold_answer": "Should be ignored.",
                "scenario_type": "standard_qa",
                "has_answer_in_corpus": "1",
                "n_eval_examples": "0",
                "is_used_in_eval": "0",
                "split": "train",
                "difficulty_level": "easy",
                "use_case": "rag_evaluation",
            },
        ],
    )

    _write_csv(
        data_dir / "rag_corpus_documents.csv",
        ["doc_id", "title"],
        [
            {"doc_id": "DOC0001", "title": "Auth guide"},
            {"doc_id": "DOC0002", "title": "Other guide"},
        ],
    )

    _write_csv(
        data_dir / "rag_corpus_chunks.csv",
        ["chunk_id", "doc_id", "domain", "chunk_index", "estimated_tokens", "chunk_text"],
        [
            {
                "chunk_id": "C00001",
                "doc_id": "DOC0001",
                "domain": "developer_docs",
                "chunk_index": "1",
                "estimated_tokens": "10",
                "chunk_text": "Bearer tokens authenticate API requests.",
            },
            {
                "chunk_id": "C00002",
                "doc_id": "DOC0001",
                "domain": "developer_docs",
                "chunk_index": "0",
                "estimated_tokens": "8",
                "chunk_text": "API keys are passed as a bearer token.",
            },
        ],
    )

    return tmp_path


def test_load_test_dataset_scenarios_filters_and_assembles_document(tmp_path: Path) -> None:
    dataset_dir = _bootstrap_dataset(tmp_path)

    scenarios = load_test_dataset_scenarios(dataset_dir=dataset_dir, max_scenarios=12)

    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert scenario.name == "SC0001"
    assert scenario.query == "How do I authenticate?"
    assert scenario.document_title == "Auth guide"
    assert "API keys are passed as a bearer token." in scenario.document_text
    chunk_zero = scenario.document_text.index("API keys are passed as a bearer token.")
    chunk_one = scenario.document_text.index("Bearer tokens authenticate API requests.")
    assert chunk_zero < chunk_one
    assert scenario.expected_phrases == ("API keys are passed as a bearer token",)


def test_load_test_dataset_scenarios_uses_relevant_chunk_titles_when_events_present(
    tmp_path: Path,
) -> None:
    dataset_dir = _bootstrap_dataset(tmp_path)
    data_dir = dataset_dir / "data"
    chunks_rows = list(csv.DictReader((data_dir / "rag_corpus_chunks.csv").open(encoding="utf-8")))
    for row in chunks_rows:
        if row["chunk_id"] == "C00002":
            row["chunk_text"] = (
                "In 'Auth guide for API integrations' API keys are passed as a bearer token."
            )
    _write_csv(
        data_dir / "rag_corpus_chunks.csv",
        list(chunks_rows[0].keys()),
        chunks_rows,
    )
    _write_csv(
        data_dir / "rag_retrieval_events.csv",
        [
            "run_id",
            "example_id",
            "scenario_id",
            "query_id",
            "split",
            "query_domain",
            "difficulty",
            "retrieval_strategy",
            "rank",
            "chunk_id",
            "retrieval_score",
            "is_relevant",
        ],
        [
            {
                "run_id": "run_0",
                "example_id": "QA000001",
                "scenario_id": "SC0001",
                "query_id": "Q0001",
                "split": "train",
                "query_domain": "developer_docs",
                "difficulty": "easy",
                "retrieval_strategy": "dense",
                "rank": "1",
                "chunk_id": "C00002",
                "retrieval_score": "0.9",
                "is_relevant": "1",
            }
        ],
    )

    scenarios = load_test_dataset_scenarios(dataset_dir=dataset_dir, max_scenarios=12)
    scenario = scenarios[0]
    assert scenario.name == "SC0001"
    assert scenario.expected_phrases == ("Auth guide for API integrations",)


def test_load_test_dataset_scenarios_respects_max_scenarios(tmp_path: Path) -> None:
    dataset_dir = _bootstrap_dataset(tmp_path)
    data_dir = dataset_dir / "data"
    rows = list(csv.DictReader((data_dir / "scenarios.csv").open(encoding="utf-8")))
    extra = dict(rows[0])
    extra["scenario_id"] = "SC0099"
    extra["query"] = "Second eval query"
    with (data_dir / "scenarios.csv").open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writerow(extra)

    scenarios = load_test_dataset_scenarios(dataset_dir=dataset_dir, max_scenarios=1)
    assert len(scenarios) == 1


def test_summarize_test_dataset_counts(tmp_path: Path) -> None:
    dataset_dir = _bootstrap_dataset(tmp_path)

    summary = summarize_test_dataset(dataset_dir=dataset_dir, max_scenarios=12)

    assert summary.total_scenarios == 3
    assert summary.eval_scenarios == 2
    assert summary.answer_in_corpus_scenarios == 1
    assert summary.scenario_ids == ("SC0001",)


def test_load_test_dataset_scenarios_raises_when_missing(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    with pytest.raises(TestDatasetNotFoundError, match="scenarios file not found"):
        load_test_dataset_scenarios(dataset_dir=tmp_path)


def test_summarize_test_dataset_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(TestDatasetNotFoundError, match="data directory not found"):
        summarize_test_dataset(dataset_dir=tmp_path)


def test_test_dataset_is_available_reflects_fixture_presence(tmp_path: Path) -> None:
    assert test_dataset_is_available(dataset_dir=tmp_path) is False

    dataset_dir = _bootstrap_dataset(tmp_path)
    assert test_dataset_is_available(dataset_dir=dataset_dir) is True
