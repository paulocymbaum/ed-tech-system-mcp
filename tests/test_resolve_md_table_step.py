"""Tests for recursive-loop resolve_md_table_step tool."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESOLVE_SCRIPT = REPO_ROOT / ".cursor/skills/recursive-loop/scripts/resolve-md-table-step.sh"
LOOP_FIXTURE = REPO_ROOT / "tests/fixtures/recursive_loop_action_summary.md"


def _resolve(**kwargs: str) -> subprocess.CompletedProcess[str]:
    args = [
        "bash",
        str(RESOLVE_SCRIPT),
        "--file",
        kwargs.get("file", str(LOOP_FIXTURE.relative_to(REPO_ROOT))),
        "--section",
        kwargs.get("section", "Action summary"),
    ]
    if "loop_break" in kwargs:
        args.extend(["--loop-break", kwargs["loop_break"]])
    if "skip_type" in kwargs:
        args.extend(["--skip-type", kwargs["skip_type"]])
    return subprocess.run(args, text=True, capture_output=True, cwd=REPO_ROOT, check=False)


def test_returns_first_action_summary_table_row() -> None:
    result = _resolve()
    assert result.returncode == 0, result.stderr
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("| RF01 |")
    assert lines[0].endswith("|")
    assert ":---" not in lines[0]
    assert lines[1] == "RF01: Delete Vercel serverless entrypoint"


def test_skips_defer_type_rows_when_requested() -> None:
    loop_break = REPO_ROOT / "changelog/2026-08-01/refactor/LOOP_BREAK_TEST_DEFER.md"
    loop_break.write_text(
        """# Loop Break Parameters TEST

## Iteration log

| Iteration | Timestamp | verify exit | master_prompt | master result | doc_sync |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | 2026-08-01 | 0 | prompt | RF01 done | — |
| 1 | 2026-08-01 | 0 | prompt | RF02 done | — |
| 2 | 2026-08-01 | 0 | prompt | RF03 done | — |
| 3 | 2026-08-01 | 0 | prompt | RF04 done | — |
| 4 | 2026-08-01 | 0 | prompt | RF05 done | — |
| 5 | 2026-08-01 | 0 | prompt | RF06 done | — |
| 6 | 2026-08-01 | 0 | prompt | RF07 done | — |
| 7 | 2026-08-01 | 0 | prompt | RF08 done | — |
| 8 | 2026-08-01 | 0 | prompt | RF09 done | — |
| 9 | 2026-08-01 | 0 | prompt | RF10 done | — |
| 10 | 2026-08-01 | 0 | prompt | RF11 done | — |
| 11 | 2026-08-01 | 0 | prompt | RF12 done | — |
| 12 | 2026-08-01 | 0 | prompt | RF13 done | — |
| 13 | 2026-08-01 | 0 | prompt | RF14 done | — |
| 14 | 2026-08-01 | 0 | prompt | RF15 done | — |
| 15 | 2026-08-01 | 0 | prompt | RF16 done | — |
| 16 | 2026-08-01 | 0 | prompt | RF17 done | — |
| 17 | 2026-08-01 | 0 | prompt | RF20 done | — |
| 18 | 2026-08-01 | 0 | prompt | RF21 done | — |
| 19 | 2026-08-01 | 0 | prompt | RF22 done | — |
| 20 | 2026-08-01 | 0 | prompt | RF23 done | — |
| 21 | 2026-08-01 | 0 | prompt | RF24 done | — |
| 22 | 2026-08-01 | 0 | prompt | RF25 done | — |
| 23 | 2026-08-01 | 0 | prompt | RF26 done | — |
| 24 | 2026-08-01 | 0 | prompt | RF27 done | — |
| 25 | 2026-08-01 | 0 | prompt | RF28 done | — |
""",
        encoding="utf-8",
    )
    try:
        result = _resolve(
            loop_break=str(loop_break.relative_to(REPO_ROOT)),
            skip_type="DEFER",
        )
        assert result.returncode == 1, result.stdout
        assert "no remaining actionable row" in result.stderr
    finally:
        loop_break.unlink(missing_ok=True)


def test_skips_ids_from_loop_break_log() -> None:
    loop_break = REPO_ROOT / "changelog/2026-08-01/refactor/LOOP_BREAK_TEST_SKIP.md"
    loop_break.write_text(
        """# Loop Break Parameters TEST

## Iteration log

| Iteration | Timestamp | verify exit | master_prompt | master result | doc_sync |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | 2026-08-01 | 0 | prompt | RF01 done | — |
""",
        encoding="utf-8",
    )
    try:
        result = _resolve(
            file=str(LOOP_FIXTURE.relative_to(REPO_ROOT)),
            loop_break=str(loop_break.relative_to(REPO_ROOT)),
        )
        assert result.returncode == 0, result.stderr
        lines = result.stdout.strip().splitlines()
        assert lines[0].startswith("| RF02 |")
        assert lines[1].startswith("RF02:")
    finally:
        loop_break.unlink(missing_ok=True)


def test_missing_file_returns_error() -> None:
    result = _resolve(file="changelog/does-not-exist.md")
    assert result.returncode == 2


def test_missing_section_returns_error() -> None:
    result = _resolve(section="Not A Real Section")
    assert result.returncode == 1
