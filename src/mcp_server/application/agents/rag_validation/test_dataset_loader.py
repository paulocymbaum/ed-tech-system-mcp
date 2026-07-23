"""Load RAG benchmark scenarios from the bundled test-dataset CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from mcp_server.application.agents.rag_validation.fixture import resolve_repo_root
from mcp_server.application.agents.rag_validation.scenarios import RagSearchScenario
from mcp_server.domain.optimization_report import (
    derive_expected_phrases_from_chunk_texts,
    derive_expected_phrases_from_gold_answer,
    filter_phrases_present_in_document,
)

DEFAULT_MAX_SCENARIOS = 12
TEST_DATASET_DIR = resolve_repo_root() / "test-dataset"
TEST_DATASET_DATA_DIR = TEST_DATASET_DIR / "data"

_TEST_DATASET_SETUP_HINT = (
    "The bundled test-dataset/ directory is required for CSV-based RAG optimization. "
    "Obtain it from the project maintainers, or use JSON scenarios via "
    "--scenarios / load_search_scenarios instead."
)


class TestDatasetNotFoundError(FileNotFoundError):
    """Raised when the bundled test-dataset directory or required CSV files are missing."""

    __test__ = False


def test_dataset_is_available(dataset_dir: str | Path | None = None) -> bool:
    """Return True when the test-dataset data directory and scenarios.csv exist."""
    data_dir = resolve_test_dataset_dir(dataset_dir) / "data"
    return data_dir.is_dir() and (data_dir / "scenarios.csv").is_file()


@dataclass(frozen=True, slots=True)
class TestDatasetSummary:
    """Counts exposed to the Benchmark UI before optimization."""

    total_scenarios: int
    eval_scenarios: int
    answer_in_corpus_scenarios: int
    default_max_scenarios: int
    scenario_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, int | list[str]]:
        return {
            "total_scenarios": self.total_scenarios,
            "eval_scenarios": self.eval_scenarios,
            "answer_in_corpus_scenarios": self.answer_in_corpus_scenarios,
            "default_max_scenarios": self.default_max_scenarios,
            "scenario_ids": list(self.scenario_ids),
        }


def resolve_test_dataset_dir(path: str | Path | None = None) -> Path:
    if path is None:
        return TEST_DATASET_DIR
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolve_repo_root() / candidate
    return candidate


def load_test_dataset_scenarios(
    *,
    dataset_dir: str | Path | None = None,
    max_scenarios: int | None = DEFAULT_MAX_SCENARIOS,
) -> list[RagSearchScenario]:
    """Load filtered eval scenarios with corpus text assembled from CSV chunks."""
    data_dir = resolve_test_dataset_dir(dataset_dir) / "data"
    scenarios_path = data_dir / "scenarios.csv"
    documents_path = data_dir / "rag_corpus_documents.csv"
    chunks_path = data_dir / "rag_corpus_chunks.csv"

    _require_test_dataset_files(data_dir, scenarios_path=scenarios_path)

    titles = _load_document_titles(documents_path)
    chunks_by_doc = _load_chunks_by_document(chunks_path)
    chunks_by_id = _load_chunks_by_id(chunks_path)
    relevant_chunks_by_scenario = _load_relevant_chunks_by_scenario(
        data_dir / "rag_retrieval_events.csv",
    )
    filtered_rows = _load_filtered_scenario_rows(scenarios_path)

    if max_scenarios is not None and max_scenarios >= 0:
        filtered_rows = filtered_rows[:max_scenarios]

    scenarios: list[RagSearchScenario] = []
    for row in filtered_rows:
        scenario = _scenario_from_row(
            row,
            titles=titles,
            chunks_by_doc=chunks_by_doc,
            chunks_by_id=chunks_by_id,
            relevant_chunks_by_scenario=relevant_chunks_by_scenario,
        )
        if scenario is not None:
            scenarios.append(scenario)
    return scenarios


def summarize_test_dataset(
    *,
    dataset_dir: str | Path | None = None,
    max_scenarios: int | None = DEFAULT_MAX_SCENARIOS,
) -> TestDatasetSummary:
    """Return scenario counts for the Benchmark UI."""
    data_dir = resolve_test_dataset_dir(dataset_dir) / "data"
    scenarios_path = data_dir / "scenarios.csv"
    _require_test_dataset_files(data_dir, scenarios_path=scenarios_path)

    rows = list(csv.DictReader(scenarios_path.open(encoding="utf-8")))
    eval_rows = [row for row in rows if _flag_is_set(row.get("is_used_in_eval"))]
    answer_rows = [row for row in eval_rows if _flag_is_set(row.get("has_answer_in_corpus"))]
    capped = answer_rows
    if max_scenarios is not None and max_scenarios >= 0:
        capped = answer_rows[:max_scenarios]

    return TestDatasetSummary(
        total_scenarios=len(rows),
        eval_scenarios=len(eval_rows),
        answer_in_corpus_scenarios=len(answer_rows),
        default_max_scenarios=max_scenarios if max_scenarios is not None else DEFAULT_MAX_SCENARIOS,
        scenario_ids=tuple(str(row["scenario_id"]) for row in capped),
    )


def _require_test_dataset_files(data_dir: Path, *, scenarios_path: Path) -> None:
    if not data_dir.is_dir():
        msg = f"Test dataset data directory not found: {data_dir}\n{_TEST_DATASET_SETUP_HINT}"
        raise TestDatasetNotFoundError(msg)
    if not scenarios_path.is_file():
        msg = f"Test dataset scenarios file not found: {scenarios_path}\n{_TEST_DATASET_SETUP_HINT}"
        raise TestDatasetNotFoundError(msg)


def _load_filtered_scenario_rows(scenarios_path: Path) -> list[dict[str, str]]:
    rows = list(csv.DictReader(scenarios_path.open(encoding="utf-8")))
    return [
        row
        for row in rows
        if _flag_is_set(row.get("is_used_in_eval"))
        and _flag_is_set(row.get("has_answer_in_corpus"))
    ]


def _load_document_titles(documents_path: Path) -> dict[str, str]:
    if not documents_path.is_file():
        return {}
    titles: dict[str, str] = {}
    for row in csv.DictReader(documents_path.open(encoding="utf-8")):
        doc_id = str(row.get("doc_id", "")).strip()
        if doc_id:
            titles[doc_id] = str(row.get("title", "")).strip()
    return titles


def _load_chunks_by_id(chunks_path: Path) -> dict[str, tuple[str, str]]:
    if not chunks_path.is_file():
        return {}
    chunks_by_id: dict[str, tuple[str, str]] = {}
    for row in csv.DictReader(chunks_path.open(encoding="utf-8")):
        chunk_id = str(row.get("chunk_id", "")).strip()
        doc_id = str(row.get("doc_id", "")).strip()
        if not chunk_id or not doc_id:
            continue
        chunks_by_id[chunk_id] = (doc_id, str(row.get("chunk_text", "")))
    return chunks_by_id


def _load_relevant_chunks_by_scenario(events_path: Path) -> dict[str, set[str]]:
    if not events_path.is_file():
        return {}
    relevant: dict[str, set[str]] = {}
    for row in csv.DictReader(events_path.open(encoding="utf-8")):
        if not _flag_is_set(row.get("is_relevant")):
            continue
        scenario_id = str(row.get("scenario_id", "")).strip()
        chunk_id = str(row.get("chunk_id", "")).strip()
        if not scenario_id or not chunk_id:
            continue
        relevant.setdefault(scenario_id, set()).add(chunk_id)
    return relevant


def _load_chunks_by_document(chunks_path: Path) -> dict[str, list[tuple[int, str]]]:
    if not chunks_path.is_file():
        return {}
    chunks_by_doc: dict[str, list[tuple[int, str]]] = {}
    for row in csv.DictReader(chunks_path.open(encoding="utf-8")):
        doc_id = str(row.get("doc_id", "")).strip()
        if not doc_id:
            continue
        chunk_index = int(row.get("chunk_index", 0))
        chunk_text = str(row.get("chunk_text", ""))
        chunks_by_doc.setdefault(doc_id, []).append((chunk_index, chunk_text))
    for doc_id, chunks in chunks_by_doc.items():
        chunks_by_doc[doc_id] = sorted(chunks, key=lambda item: item[0])
    return chunks_by_doc


def _scenario_from_row(
    row: dict[str, str],
    *,
    titles: dict[str, str],
    chunks_by_doc: dict[str, list[tuple[int, str]]],
    chunks_by_id: dict[str, tuple[str, str]],
    relevant_chunks_by_scenario: dict[str, set[str]],
) -> RagSearchScenario | None:
    scenario_id = str(row.get("scenario_id", "")).strip() or "scenario"
    query = str(row.get("query", "")).strip()
    gold_answer = str(row.get("gold_answer", "")).strip()
    primary_doc_id = str(row.get("primary_doc_id", "")).strip()

    if not query:
        return None

    doc_chunks = chunks_by_doc.get(primary_doc_id, [])
    if not doc_chunks:
        return None

    document_text = "\n\n".join(chunk_text for _, chunk_text in doc_chunks)
    expected_phrases = _expected_phrases_for_scenario(
        scenario_id=scenario_id,
        gold_answer=gold_answer,
        primary_doc_id=primary_doc_id,
        document_text=document_text,
        chunks_by_id=chunks_by_id,
        relevant_chunks_by_scenario=relevant_chunks_by_scenario,
    )
    if not expected_phrases:
        return None

    document_title = titles.get(primary_doc_id) or primary_doc_id

    return RagSearchScenario(
        name=scenario_id,
        query=query,
        expected_phrases=expected_phrases,
        document_text=document_text,
        document_title=document_title,
        gold_answer=gold_answer or None,
    )


def _expected_phrases_for_scenario(
    *,
    scenario_id: str,
    gold_answer: str,
    primary_doc_id: str,
    document_text: str,
    chunks_by_id: dict[str, tuple[str, str]],
    relevant_chunks_by_scenario: dict[str, set[str]],
) -> tuple[str, ...]:
    relevant_chunk_ids = relevant_chunks_by_scenario.get(scenario_id, set())
    relevant_texts = [
        chunks_by_id[chunk_id][1]
        for chunk_id in relevant_chunk_ids
        if chunk_id in chunks_by_id and chunks_by_id[chunk_id][0] == primary_doc_id
    ]
    if relevant_texts:
        phrases = derive_expected_phrases_from_chunk_texts(relevant_texts)
        if phrases:
            return filter_phrases_present_in_document(phrases, document_text)

    return filter_phrases_present_in_document(
        derive_expected_phrases_from_gold_answer(gold_answer),
        document_text,
    )


def _flag_is_set(value: object) -> bool:
    return str(value).strip() == "1"
