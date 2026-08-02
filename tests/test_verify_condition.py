"""Tests for recursive-loop verify_condition bash tool."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.cursor_harness

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = (
    REPO_ROOT / ".cursor/skills/recursive-loop/scripts/verify-condition.sh"
)


def _run(script: str | None = None, *, arg: str | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = ["bash", str(VERIFY_SCRIPT)]
    if arg is not None:
        cmd.append(arg)
    return subprocess.run(
        cmd,
        input=script,
        text=True,
        capture_output=True,
        cwd=REPO_ROOT,
        env=env,
        check=False,
    )


def test_true_condition_via_arg() -> None:
    result = _run(arg="true")
    assert result.returncode == 0


def test_false_condition_via_arg() -> None:
    result = _run(arg="false")
    assert result.returncode == 1


def test_true_condition_via_stdin() -> None:
    result = _run("exit 0")
    assert result.returncode == 0


def test_false_condition_via_stdin() -> None:
    result = _run("exit 5")
    assert result.returncode == 1


def test_empty_input_returns_tool_error() -> None:
    result = _run("")
    assert result.returncode == 2
    assert "empty" in result.stderr.lower()


def test_whitespace_only_input_returns_tool_error() -> None:
    result = _run("   \n  ")
    assert result.returncode == 2


def test_file_existence_check_true() -> None:
    result = _run(arg=f"test -f {VERIFY_SCRIPT}")
    assert result.returncode == 0


def test_file_existence_check_false() -> None:
    result = _run(arg="test -f /nonexistent/path/for/verify-condition-test")
    assert result.returncode == 1


@pytest.mark.skipif(shutil.which("timeout") is None, reason="timeout command not available")
def test_timeout_returns_tool_error() -> None:
    env = os.environ.copy()
    env["VERIFY_CONDITION_TIMEOUT"] = "1"
    result = _run("sleep 5", env=env)
    assert result.returncode == 2
    assert "timed out" in result.stderr.lower()
