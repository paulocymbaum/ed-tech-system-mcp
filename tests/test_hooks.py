"""Tests for Husky pre-commit and pre-push safety hooks."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_FILES = REPO_ROOT / "scripts/hooks/sensitive-files.sh"
BLOCK_SENSITIVE_FILES = REPO_ROOT / "scripts/hooks/block-sensitive-files.sh"
SCAN_SECRETS = REPO_ROOT / "scripts/hooks/scan-secrets.sh"
SCAN_ALLOWLIST = REPO_ROOT / "scripts/hooks/scan-allowlist.sh"
SCAN_PUSH_SECRETS = REPO_ROOT / "scripts/hooks/scan-push-secrets.sh"
SCAN_ENTROPY = REPO_ROOT / "scripts/hooks/scan-entropy.sh"
SCAN_STAGED_CONTENT = REPO_ROOT / "scripts/hooks/scan-staged-content.sh"
CHECK_TRACKED_SENSITIVE = REPO_ROOT / "scripts/hooks/check-tracked-sensitive.sh"
VERIFY_GITIGNORE = REPO_ROOT / "scripts/hooks/verify-gitignore.sh"
PRE_COMMIT = REPO_ROOT / "scripts/hooks/pre-commit.sh"
PRE_PUSH_SAFETY = REPO_ROOT / "scripts/hooks/pre-push-safety.sh"


def _leaked_github_token_content() -> str:
    token = "gh" + "p_" + "a" * 36
    return f"API_KEY = '{token}'\n"


def _leaked_groq_token_content() -> str:
    token = "gs" + "k_" + "a" * 24
    return f'API_KEY = "{token}"\n'


def _leaked_aws_key_content() -> str:
    key_id = "AK" + "IA" + "IOSFODNN7EXAMPLE"
    return f'AWS_ACCESS_KEY_ID = "{key_id}"\n'


def _init_test_repo(repo_dir: Path) -> None:
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


def _write_gitignore(repo_dir: Path) -> None:
    """Minimal .gitignore matching required patterns for verify-gitignore."""
    gitignore = repo_dir / ".gitignore"
    gitignore.write_text(
        "\n".join(
            [
                ".env",
                ".env.*",
                "*.env",
                "*.env.*",
                ".ENV",
                ".ENV.*",
                "*.ENV",
                "*.ENV.*",
                "scripts/doppler/*.env",
                ".venv/",
                "id_rsa",
                "id_ed25519",
                ".npmrc",
                ".pypirc",
                "*.p8",
                "*.jks",
                "changelog/",
                "mcp.json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _copy_hooks_to_repo(repo_dir: Path) -> None:
    hooks_src = REPO_ROOT / "scripts/hooks"
    hooks_dst = repo_dir / "scripts/hooks"
    if hooks_dst.exists():
        shutil.rmtree(hooks_dst)
    shutil.copytree(hooks_src, hooks_dst)
    for script in hooks_dst.rglob("*.sh"):
        script.chmod(0o755)


def _stage_file(repo_dir: Path, relative_path: str, *, force: bool = False) -> None:
    args = ["git", "add"]
    if force:
        args.append("-f")
    args.append(relative_path)
    subprocess.run(args, cwd=repo_dir, check=True, capture_output=True, text=True)


def _run_hook_in_repo(
    repo_dir: Path, hook_script: Path, *staged_paths: str, content: str = "staged-for-hook-test\n"
) -> subprocess.CompletedProcess[str]:
    _init_test_repo(repo_dir)
    _write_gitignore(repo_dir)
    _copy_hooks_to_repo(repo_dir)
    subprocess.run(
        ["git", "add", ".gitignore"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "seed gitignore", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    for relative_path in staged_paths:
        file_path = repo_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        _stage_file(repo_dir, relative_path, force=True)

    return subprocess.run(
        ["bash", str(hook_script)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )


def test_block_sensitive_files_rejects_dotenv(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, ".env")
    assert result.returncode == 1
    assert "sensitive files staged" in result.stderr


def test_block_sensitive_files_rejects_uppercase_dotenv(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, ".ENV")
    assert result.returncode == 1
    assert ".ENV" in result.stderr


def test_block_sensitive_files_rejects_mixed_case_env_extension(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, "config.Env")
    assert result.returncode == 1
    assert "config.Env" in result.stderr


def test_block_sensitive_files_rejects_credentials_json(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, "credentials.json")
    assert result.returncode == 1
    assert "credentials.json" in result.stderr


def test_block_sensitive_files_rejects_doppler_env(tmp_path: Path) -> None:
    result = _run_hook_in_repo(
        tmp_path, BLOCK_SENSITIVE_FILES, "scripts/doppler/secrets.dev.env"
    )
    assert result.returncode == 1
    assert "scripts/doppler/secrets.dev.env" in result.stderr


def test_block_sensitive_files_rejects_ssh_key(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, "id_rsa")
    assert result.returncode == 1
    assert "id_rsa" in result.stderr


def test_block_sensitive_files_rejects_npmrc(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, ".npmrc")
    assert result.returncode == 1
    assert ".npmrc" in result.stderr


def test_block_sensitive_files_rejects_mcp_json(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, "mcp.json")
    assert result.returncode == 1
    assert "mcp.json" in result.stderr


def test_block_sensitive_files_rejects_changelog_force_add(tmp_path: Path) -> None:
    result = _run_hook_in_repo(
        tmp_path, BLOCK_SENSITIVE_FILES, "changelog/2026-07-28/entrypoint/INVESTIGATION1.md"
    )
    assert result.returncode == 1
    assert "changelog/" in result.stderr


def test_block_sensitive_files_allows_py_files(tmp_path: Path) -> None:
    result = _run_hook_in_repo(tmp_path, BLOCK_SENSITIVE_FILES, "src/foo.py")
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_check_tracked_sensitive_rejects_committed_env(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_test_repo(repo_dir)
    _write_gitignore(repo_dir)
    _copy_hooks_to_repo(repo_dir)
    env_file = repo_dir / ".env"
    env_file.write_text("SECRET=bad\n", encoding="utf-8")
    _stage_file(repo_dir, ".gitignore")
    _stage_file(repo_dir, ".env", force=True)
    subprocess.run(
        ["git", "commit", "-m", "bad env", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        ["bash", str(CHECK_TRACKED_SENSITIVE)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "sensitive files tracked" in result.stderr
    assert ".env" in result.stderr


def test_verify_gitignore_rejects_missing_required_pattern(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_test_repo(repo_dir)
    gitignore = repo_dir / ".gitignore"
    gitignore.write_text(
        "\n".join(
            [
                ".env",
                ".env.*",
                "*.env",
                "*.env.*",
                ".ENV",
                ".ENV.*",
                "*.ENV",
                "*.ENV.*",
                "scripts/doppler/*.env",
                ".venv/",
                "id_rsa",
                "id_ed25519",
                ".npmrc",
                ".pypirc",
                "*.p8",
                "*.jks",
                "mcp.json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _copy_hooks_to_repo(repo_dir)
    subprocess.run(
        ["git", "add", ".gitignore"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "seed gitignore", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        ["bash", str(VERIFY_GITIGNORE)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "missing patterns" in result.stderr
    assert "changelog/" in result.stderr


def test_verify_gitignore_rejects_tracked_ignored_file(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_test_repo(repo_dir)
    _write_gitignore(repo_dir)
    _copy_hooks_to_repo(repo_dir)
    env_file = repo_dir / ".env"
    env_file.write_text("SECRET=bad\n", encoding="utf-8")
    _stage_file(repo_dir, ".gitignore")
    _stage_file(repo_dir, ".env", force=True)
    subprocess.run(
        ["git", "commit", "-m", "bad env", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        ["bash", str(VERIFY_GITIGNORE)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "tracked files match .gitignore" in result.stderr
    assert ".env" in result.stderr


def test_scan_entropy_rejects_known_token_prefix(tmp_path: Path) -> None:
    result = _run_hook_in_repo(
        tmp_path,
        SCAN_ENTROPY,
        "config.py",
        content=_leaked_github_token_content(),
    )
    assert result.returncode == 1
    assert "potential secrets" in result.stderr.lower()


def test_scan_entropy_allows_safe_content(tmp_path: Path) -> None:
    result = _run_hook_in_repo(
        tmp_path,
        SCAN_ENTROPY,
        "src/foo.py",
        content="def hello():\n    return 'world'\n",
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_scan_staged_content_rejects_groq_key(tmp_path: Path) -> None:
    result = _run_hook_in_repo(
        tmp_path,
        SCAN_STAGED_CONTENT,
        "config.py",
        content=_leaked_groq_token_content(),
    )
    assert result.returncode == 1
    assert "potential secrets" in result.stderr.lower()


def test_sensitive_files_library_is_not_gitignored() -> None:
    assert SENSITIVE_FILES.is_file(), "shared sensitive-files.sh must exist for fresh clones"
    result = subprocess.run(
        ["git", "check-ignore", "-q", "scripts/hooks/sensitive-files.sh"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, "sensitive-files.sh must be committable (not matched by lib/ gitignore)"


def test_scan_allowlist_is_not_gitignored() -> None:
    assert SCAN_ALLOWLIST.is_file(), "scan-allowlist.sh must exist for fresh clones"
    result = subprocess.run(
        ["git", "check-ignore", "-q", "scripts/hooks/scan-allowlist.sh"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, "scan-allowlist.sh must be committable (not matched by lib/ gitignore)"


def test_test_hooks_fixture_tokens_avoid_literal_secret_prefixes() -> None:
    content = (REPO_ROOT / "tests/test_hooks.py").read_text(encoding="utf-8")
    fixture_section = content.split("def test_block_sensitive_files_rejects_dotenv", maxsplit=1)[0]
    for literal in ("ghp_", "gsk_", "AKIA"):
        assert literal not in fixture_section, (
            f"hook test fixtures must build {literal!r} via concatenation so scanners do not false-positive"
        )


def test_scan_staged_content_rejects_aws_access_key(tmp_path: Path) -> None:
    result = _run_hook_in_repo(
        tmp_path,
        SCAN_STAGED_CONTENT,
        "config.py",
        content=_leaked_aws_key_content(),
    )
    assert result.returncode == 1
    assert "potential secrets" in result.stderr.lower()


def test_scan_secrets_runs_all_available_scanners(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_test_repo(repo_dir)
    _write_gitignore(repo_dir)
    _copy_hooks_to_repo(repo_dir)
    subprocess.run(
        ["git", "add", ".gitignore"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "seed", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    safe_file = repo_dir / "src/safe.py"
    safe_file.parent.mkdir(parents=True, exist_ok=True)
    safe_file.write_text("def ok():\n    return True\n", encoding="utf-8")
    _stage_file(repo_dir, "src/safe.py")

    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    gitleaks = fake_bin / "gitleaks"
    gitleaks.write_text("#!/usr/bin/env bash\necho fake-gitleaks\nexit 0\n", encoding="utf-8")
    gitleaks.chmod(0o755)

    secretlint = repo_dir / "node_modules/.bin/secretlint"
    secretlint.parent.mkdir(parents=True, exist_ok=True)
    secretlint.write_text("#!/usr/bin/env bash\necho fake-secretlint\nexit 0\n", encoding="utf-8")
    secretlint.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = subprocess.run(
        ["bash", str(repo_dir / "scripts/hooks/scan-secrets.sh")],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == ""
    assert result.stderr == ""


def test_scan_secrets_skips_deleted_staged_files(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _init_test_repo(repo_dir)
    _write_gitignore(repo_dir)
    _copy_hooks_to_repo(repo_dir)
    subprocess.run(
        ["git", "add", ".gitignore"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "seed", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    tracked = repo_dir / "tracked.txt"
    tracked.write_text("safe content\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "tracked.txt"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "seed tracked", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    tracked.unlink()
    subprocess.run(
        ["git", "add", "tracked.txt"], cwd=repo_dir, check=True, capture_output=True, text=True
    )

    result = subprocess.run(
        ["bash", str(SCAN_SECRETS)],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == ""
    assert result.stderr == ""


def test_scan_secrets_falls_back_to_staged_content_when_no_scanners(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_test_repo(repo_dir)
    _write_gitignore(repo_dir)
    _copy_hooks_to_repo(repo_dir)
    subprocess.run(
        ["git", "add", ".gitignore"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "seed", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    secret_file = repo_dir / "config.py"
    secret_file.write_text(_leaked_groq_token_content(), encoding="utf-8")
    _stage_file(repo_dir, "config.py")

    env = os.environ.copy()
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env["PATH"] = f"{empty_bin}:/usr/bin:/bin"

    result = subprocess.run(
        ["/usr/bin/bash", str(repo_dir / "scripts/hooks/scan-secrets.sh")],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 1, result.stderr or result.stdout
    assert "potential secrets" in result.stderr.lower()


def test_scan_push_secrets_rejects_leaked_token_in_push_range(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    _init_test_repo(repo_dir)
    _write_gitignore(repo_dir)
    _copy_hooks_to_repo(repo_dir)
    subprocess.run(
        ["git", "add", ".gitignore"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "seed", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    secret_file = repo_dir / "config.py"
    secret_file.write_text(_leaked_groq_token_content(), encoding="utf-8")
    subprocess.run(
        ["git", "add", "config.py"], cwd=repo_dir, check=True, capture_output=True, text=True
    )
    subprocess.run(
        ["git", "commit", "-m", "bad secret", "--no-verify"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )

    local_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    zero_sha = "0" * 40

    env = os.environ.copy()
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env["PATH"] = f"{empty_bin}:/usr/bin:/bin"

    result = subprocess.run(
        ["/usr/bin/bash", str(repo_dir / "scripts/hooks/scan-push-secrets.sh")],
        cwd=repo_dir,
        input=f"refs/heads/main {local_sha} refs/heads/main {zero_sha}\n",
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 1, result.stderr or result.stdout
    assert "potential secrets" in result.stderr.lower()


@pytest.mark.skipif(not PRE_COMMIT.is_file(), reason="pre-commit hook script missing")
def test_pre_commit_passes_on_clean_tree() -> None:
    result = subprocess.run(
        ["bash", str(PRE_COMMIT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.skipif(not PRE_PUSH_SAFETY.is_file(), reason="pre-push safety script missing")
def test_pre_push_safety_passes_on_clean_tree() -> None:
    result = subprocess.run(
        ["bash", str(PRE_PUSH_SAFETY)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert result.stdout == ""
    assert result.stderr == ""
