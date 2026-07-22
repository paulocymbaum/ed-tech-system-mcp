"""Tests for architecture linter scripts and import-linter contracts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATTERNS = REPO_ROOT / "scripts/lint/check-boundary-patterns.sh"
ARCHITECTURE_LINT = REPO_ROOT / "scripts/lint/architecture.sh"


def _run_script(
    script: Path, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", str(script)],
        cwd=REPO_ROOT,
        env=merged_env,
        capture_output=True,
        text=True,
    )


def test_lint_imports_passes_on_current_tree() -> None:
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/lint/lint-imports.sh")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "0 broken" in result.stdout


def test_lint_imports_works_from_subdirectory() -> None:
    ui_dir = REPO_ROOT / "ui"
    if not ui_dir.is_dir():
        pytest.skip("ui/ directory is not present")

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts/lint/lint-imports.sh")],
        cwd=ui_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "0 broken" in result.stdout


def test_boundary_patterns_pass_on_current_tree() -> None:
    result = _run_script(BOUNDARY_PATTERNS)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "Architecture boundary patterns passed" in result.stdout


def test_boundary_patterns_detects_infra_in_interface(tmp_path: Path) -> None:
    fixture_root = tmp_path / "mcp_server"
    bad_file = fixture_root / "interface" / "bad.py"
    bad_file.parent.mkdir(parents=True)
    bad_file.write_text(
        "from mcp_server.infrastructure.supabase_client import SupabaseRepository\n",
        encoding="utf-8",
    )

    result = _run_script(BOUNDARY_PATTERNS, env={"ARCHITECTURE_LINT_ROOT": str(fixture_root)})
    assert result.returncode == 1
    assert "infra-adapter-in-interface" in result.stderr
    assert "SupabaseRepository" in result.stderr


def test_boundary_patterns_detects_load_dotenv_outside_main(tmp_path: Path) -> None:
    fixture_root = tmp_path / "mcp_server"
    bad_file = fixture_root / "application" / "bad.py"
    bad_file.parent.mkdir(parents=True)
    bad_file.write_text("from dotenv import load_dotenv\nload_dotenv()\n", encoding="utf-8")

    result = _run_script(BOUNDARY_PATTERNS, env={"ARCHITECTURE_LINT_ROOT": str(fixture_root)})
    assert result.returncode == 1
    assert "load-dotenv-outside-main" in result.stderr


def test_boundary_patterns_detects_settings_import_outside_entrypoint(tmp_path: Path) -> None:
    fixture_root = tmp_path / "mcp_server"
    bad_file = fixture_root / "application" / "bad.py"
    bad_file.parent.mkdir(parents=True)
    bad_file.write_text("from mcp_server.settings import Settings\n", encoding="utf-8")

    result = _run_script(BOUNDARY_PATTERNS, env={"ARCHITECTURE_LINT_ROOT": str(fixture_root)})
    assert result.returncode == 1
    assert "settings-import-outside-entrypoint" in result.stderr


def test_architecture_script_orchestrator_passes() -> None:
    result = _run_script(ARCHITECTURE_LINT)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "All architecture lint checks passed." in result.stdout
