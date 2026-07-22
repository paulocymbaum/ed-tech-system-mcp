"""Tests for Husky pre-commit safety hooks."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BLOCK_SENSITIVE_FILES = REPO_ROOT / "scripts/hooks/block-sensitive-files.sh"
SCAN_SECRETS = REPO_ROOT / "scripts/hooks/scan-secrets.sh"
PRE_COMMIT = REPO_ROOT / "scripts/hooks/pre-commit.sh"


def _run_hook_in_repo(repo_dir: Path, hook_script: Path, *staged_paths: str) -> subprocess.CompletedProcess[str]:
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "hooks-test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Hooks Test"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    for relative_path in staged_paths:
        file_path = repo_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("staged-for-hook-test\n", encoding="utf-8")
        subprocess.run(["git", "add", relative_path], cwd=repo_dir, check=True, capture_output=True, text=True)

    return subprocess.run(
        ["bash", str(hook_script)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )


def test_block_sensitive_files_rejects_dotenv(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, ".env")
    assert result.returncode == 1
    assert "Refusing to commit sensitive files" in result.stderr


def test_block_sensitive_files_rejects_credentials_json(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, "credentials.json")
    assert result.returncode == 1
    assert "credentials.json" in result.stderr


def test_block_sensitive_files_rejects_doppler_env(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, "scripts/doppler/secrets.dev.env")
    assert result.returncode == 1
    assert "scripts/doppler/secrets.dev.env" in result.stderr


def test_block_sensitive_files_allows_py_files(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, "src/foo.py")
    assert result.returncode == 0
    assert "No sensitive files staged" in result.stdout


def test_scan_secrets_skips_deleted_staged_files(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "hooks-test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Hooks Test"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    tracked = repo_dir / "tracked.txt"
    tracked.write_text("safe content\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo_dir, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "seed", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    tracked.unlink()
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo_dir, check=True, capture_output=True, text=True)

    result = subprocess.run(
        ["bash", str(SCAN_SECRETS)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "No staged files to scan" in result.stdout


@pytest.mark.skipif(not PRE_COMMIT.is_file(), reason="pre-commit hook script missing")
def test_pre_commit_passes_on_clean_tree() -> None:
    result = subprocess.run(
        ["bash", str(PRE_COMMIT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "All pre-commit safety checks passed." in result.stdout
