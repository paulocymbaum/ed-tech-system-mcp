"""Tests for recursive-loop emit_master_prompt tool."""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EMIT_SCRIPT = REPO_ROOT / ".cursor/skills/recursive-loop/scripts/emit-master-prompt.sh"


def _emit(verify_exit: int, **kwargs: str) -> subprocess.CompletedProcess[str]:
    args = [
        "bash",
        str(EMIT_SCRIPT),
        str(verify_exit),
        "--loop-break",
        kwargs.get("loop_break", "changelog/2026-08-01/refactor/LOOP_BREAK1.md"),
        "--iteration",
        kwargs.get("iteration", "2"),
        "--description",
        kwargs.get("description", "Migrate hosting to Render"),
        "--step",
        kwargs.get("step", "RF03: delete vercel.json"),
    ]
    return subprocess.run(args, text=True, capture_output=True, cwd=REPO_ROOT, check=False)


def test_true_prompt_contains_master_task() -> None:
    result = _emit(0)
    assert result.returncode == 0
    assert 'subagent_type: "master"' in result.stdout
    assert "verify TRUE" in result.stdout
    assert "more work required" in result.stdout
    assert "RF03: delete vercel.json" in result.stdout


def test_false_prompt_contains_master_task() -> None:
    result = _emit(1)
    assert result.returncode == 0
    assert 'subagent_type: "master"' in result.stdout
    assert "verify FALSE" in result.stdout
    assert "final pass" in result.stdout.lower()


def test_prompt_includes_loop_break_path() -> None:
    loop_break = "changelog/2026-08-01/refactor/LOOP_BREAK1.md"
    result = _emit(0, loop_break=loop_break)
    assert loop_break in result.stdout


def test_invalid_verify_exit_returns_error() -> None:
    result = _emit(2)
    assert result.returncode == 2


def test_missing_args_returns_error() -> None:
    result = subprocess.run(
        ["bash", str(EMIT_SCRIPT), "0"],
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 2


def test_source_md_resolves_table_row_into_prompt() -> None:
    result = subprocess.run(
        [
            "bash",
            str(EMIT_SCRIPT),
            "0",
            "--loop-break",
            "changelog/2026-08-01/refactor/LOOP_BREAK1.md",
            "--iteration",
            "1",
            "--description",
            "Migrate hosting to Render",
            "--source-md",
            "tests/fixtures/recursive_loop_action_summary.md",
            "--table-section",
            "Action summary",
            "--skip-type",
            "DEFER",
        ],
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "RF01: Delete Vercel serverless entrypoint" in result.stdout
    assert "| RF01 | Delete Vercel serverless entrypoint |" in result.stdout
    assert "Status column to DONE" in result.stdout
    assert "Source table row (verbatim)" in result.stdout
