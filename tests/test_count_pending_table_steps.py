"""Tests for recursive-loop count_pending_table_steps tool."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COUNT_SCRIPT = REPO_ROOT / ".cursor/skills/recursive-loop/scripts/count-pending-table-steps.sh"
REFACTOR2 = REPO_ROOT / "changelog/2026-08-01/refactor/REFACTOR2.md"
LOOP_FIXTURE = REPO_ROOT / "tests/fixtures/recursive_loop_action_summary.md"


def _count(**kwargs: str) -> subprocess.CompletedProcess[str]:
    args = [
        "bash",
        str(COUNT_SCRIPT),
        "--file",
        kwargs.get("file", str(REFACTOR2.relative_to(REPO_ROOT))),
        "--section",
        kwargs.get("section", "Action summary"),
    ]
    if "skip_type" in kwargs:
        args.extend(["--skip-type", kwargs["skip_type"]])
    return subprocess.run(args, text=True, capture_output=True, cwd=REPO_ROOT, check=False)


def test_refactor2_has_no_pending_action_rows() -> None:
    result = _count(skip_type="DEFER")
    assert result.returncode == 1, result.stderr
    assert result.stdout.strip() == "0"


def test_counts_pending_rows_in_loop_fixture() -> None:
    result = _count(
        file=str(LOOP_FIXTURE.relative_to(REPO_ROOT)),
        skip_type="DEFER",
    )
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) == 3


def test_returns_complete_when_all_rows_done() -> None:
    sample = REPO_ROOT / "changelog/2026-08-01/refactor/REFACTOR2_DONE_SAMPLE.md"
    sample.write_text(
        """# Sample

## Action summary

| ID | Action | Type | Location | Severity | Effort | Blocked by | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RF01 | Example | REMOVE | `foo.py` | High | trivial | — | DONE |
| RF02 | Example two | CHANGE | `bar.py` | Low | trivial | — | PASS |
""",
        encoding="utf-8",
    )
    try:
        result = _count(file=str(sample.relative_to(REPO_ROOT)))
        assert result.returncode == 1
        assert result.stdout.strip() == "0"
    finally:
        sample.unlink(missing_ok=True)


def test_skips_done_status_when_resolving_next_row() -> None:
    sample = REPO_ROOT / "changelog/2026-08-01/refactor/REFACTOR2_PARTIAL_SAMPLE.md"
    sample.write_text(
        """# Sample

## Action summary

| ID | Action | Type | Location | Severity | Effort | Blocked by | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| RF01 | First | REMOVE | `foo.py` | High | trivial | — | DONE |
| RF02 | Second | REMOVE | `bar.py` | High | trivial | — | PENDING |
""",
        encoding="utf-8",
    )
    resolve = subprocess.run(
        [
            "bash",
            str(REPO_ROOT / ".cursor/skills/recursive-loop/scripts/resolve-md-table-step.sh"),
            "--file",
            str(sample.relative_to(REPO_ROOT)),
            "--section",
            "Action summary",
        ],
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    try:
        assert resolve.returncode == 0, resolve.stderr
        lines = resolve.stdout.strip().splitlines()
        assert lines[0].startswith("| RF02 |")
        assert lines[1] == "RF02: Second"
    finally:
        sample.unlink(missing_ok=True)
