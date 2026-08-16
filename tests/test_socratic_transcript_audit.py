"""Unit tests for E18.2 tutor turn-1 dump policy."""

from __future__ import annotations

import threading

from mcp_server.domain.golden_tutor_transcripts import (
    audit_tutor_transcripts,
    load_tutor_transcript_samples,
)
from mcp_server.domain.socratic import (
    SocraticMessage,
    tutor_turn_index,
    validate_socratic_reply,
)

_DUMP = (
    "```javascript\n"
    "function parseAge(raw) {\n"
    "  const n = Number(raw);\n"
    "  if (!Number.isFinite(n) || n < 0) return null;\n"
    "  return Math.trunc(n);\n"
    "}\n"
    "```\n"
)


def test_good_turn1_sample_passes_audit() -> None:
    samples = load_tutor_transcript_samples()
    good = next(item for item in samples if item.sample_id == "good-turn1")
    check = validate_socratic_reply(
        good.reply,
        asked_full_solution=False,
        turn_index=1,
    )
    assert check["ok"] is True


def test_turn1_complete_dump_is_blocked() -> None:
    check = validate_socratic_reply(_DUMP, asked_full_solution=False, turn_index=1)
    assert check["ok"] is False
    assert any("Full solution" in err for err in check["errors"])


def test_audit_corpus_has_no_mismatches() -> None:
    assert audit_tutor_transcripts() == []


def test_score_language_still_banned() -> None:
    result = validate_socratic_reply("Nice work. Score: 90 out of 100.")
    assert result["ok"] is False


def test_asked_full_solution_allows_dump() -> None:
    check = validate_socratic_reply(_DUMP, asked_full_solution=True, turn_index=1)
    assert check["ok"] is True


def test_turn2_small_dump_not_blocked_by_turn1_rule() -> None:
    check = validate_socratic_reply(_DUMP, asked_full_solution=False, turn_index=2)
    assert check["ok"] is True


def test_tiny_snippet_without_complete_function_ok() -> None:
    check = validate_socratic_reply(
        "Try Number.isFinite.\nWhat does it return for NaN?\n",
        asked_full_solution=False,
        turn_index=1,
    )
    assert check["ok"] is True


def test_tutor_turn_index_from_history() -> None:
    assert tutor_turn_index([]) == 1
    history = [
        SocraticMessage(role="user", content="help"),
        SocraticMessage(role="assistant", content="What did you try?"),
    ]
    assert tutor_turn_index(history) == 2


def test_parallel_audits_match() -> None:
    results: list[list[str]] = []

    def worker() -> None:
        mismatches = audit_tutor_transcripts()
        results.append([item.sample_id for item in mismatches])

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    first = results[0]
    assert all(item == first for item in results)
