"""Contract tests for scripts/ci/dependency-cache.sh hash and restore logic."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_SCRIPT = REPO_ROOT / "scripts/ci/dependency-cache.sh"

CACHE_KEY_PATTERN = re.compile(
    r"^(python-hooks|python-dev|npm-root|vercel-cli|docker-mcp)-[0-9a-f]{12}$"
)

GROUPS = ("python-hooks", "python-dev", "npm-root", "vercel-cli", "docker-mcp")


def _run(
    *args: str,
    cwd: Path | None = None,
    repo_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if repo_root is not None:
        env["DEPENDENCY_CACHE_ROOT"] = str(repo_root)
    return subprocess.run(
        ["/usr/bin/bash", str(CACHE_SCRIPT), *args],
        cwd=cwd or repo_root or REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


@pytest.mark.parametrize("group", GROUPS)
def test_cache_key_format(group: str) -> None:
    result = _run("cache-key", group)
    assert result.returncode == 0, result.stderr
    key = result.stdout.strip()
    assert CACHE_KEY_PATTERN.match(key), key


@pytest.mark.parametrize("group", GROUPS)
def test_cache_key_is_deterministic(group: str) -> None:
    first = _run("cache-key", group).stdout.strip()
    second = _run("cache-key", group).stdout.strip()
    assert first == second


def test_python_groups_have_different_keys() -> None:
    hooks = _run("cache-key", "python-hooks").stdout.strip()
    dev = _run("cache-key", "python-dev").stdout.strip()
    assert hooks != dev


def test_cache_key_changes_when_lockfile_changes(tmp_path: Path) -> None:
    pyproject = REPO_ROOT / "pyproject.toml"
    uv_lock = REPO_ROOT / "uv.lock"
    package_lock = REPO_ROOT / "package-lock.json"

    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    (fake_repo / "pyproject.toml").write_text(
        pyproject.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (fake_repo / "uv.lock").write_text(uv_lock.read_text(encoding="utf-8"), encoding="utf-8")
    (fake_repo / "package-lock.json").write_text(
        package_lock.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (fake_repo / "Dockerfile").write_text(
        (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"), encoding="utf-8"
    )

    baseline = _run("cache-key", "python-hooks", repo_root=fake_repo).stdout.strip()
    (fake_repo / "uv.lock").write_text(
        uv_lock.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8"
    )
    changed = _run("cache-key", "python-hooks", repo_root=fake_repo).stdout.strip()
    assert baseline != changed


def test_package_lock_cache_key_changes(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    lock_content = (REPO_ROOT / "package-lock.json").read_text(encoding="utf-8")
    (fake_repo / "package-lock.json").write_text(lock_content, encoding="utf-8")

    baseline = _run("cache-key", "npm-root", repo_root=fake_repo).stdout.strip()
    (fake_repo / "package-lock.json").write_text(lock_content + "\n", encoding="utf-8")
    changed = _run("cache-key", "npm-root", repo_root=fake_repo).stdout.strip()
    assert baseline != changed


def test_unknown_group_fails() -> None:
    result = _run("cache-key", "not-a-group")
    assert result.returncode != 0
    assert "unknown group" in result.stderr


def test_restore_python_hooks_misses_without_venv(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    for name in ("pyproject.toml", "uv.lock", "package-lock.json", "Dockerfile"):
        src = REPO_ROOT / name
        if src.exists():
            (fake_repo / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    result = _run("restore", "python-hooks", repo_root=fake_repo)
    assert result.returncode == 1


def test_restore_npm_root_hits_with_node_modules(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    node_modules = fake_repo / "node_modules"
    node_modules.mkdir()
    (node_modules / ".package-lock.json").write_text("{}", encoding="utf-8")

    result = _run("restore", "npm-root", repo_root=fake_repo)
    assert result.returncode == 0


def test_cache_paths_python_includes_venv() -> None:
    result = _run("cache-paths", "python-dev")
    assert result.returncode == 0
    paths = result.stdout.strip().splitlines()
    assert any(path.endswith(".venv") for path in paths)


def test_cache_paths_npm_root_is_node_modules() -> None:
    result = _run("cache-paths", "npm-root")
    assert result.returncode == 0
    assert result.stdout.strip().endswith("node_modules")


def test_install_skips_when_restore_succeeds(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    node_modules = fake_repo / "node_modules"
    node_modules.mkdir()
    (node_modules / ".package-lock.json").write_text("{}", encoding="utf-8")

    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin"
    env["DEPENDENCY_CACHE_ROOT"] = str(fake_repo)
    result = subprocess.run(
        ["/usr/bin/bash", str(CACHE_SCRIPT), "install", "npm-root"],
        cwd=fake_repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "skipping install" in result.stdout
