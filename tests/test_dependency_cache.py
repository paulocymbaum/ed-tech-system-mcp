"""Contract tests for scripts/ci/dependency-cache.sh hash and restore logic."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_SCRIPT = REPO_ROOT / "scripts/ci/dependency-cache.sh"
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"
CI_DEPS_ACTION = REPO_ROOT / ".github/actions/ci-deps/action.yml"

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


def test_lockfile_change_does_not_affect_unrelated_group(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    uv_lock = REPO_ROOT / "uv.lock"
    (fake_repo / "package-lock.json").write_text(
        (REPO_ROOT / "package-lock.json").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (fake_repo / "uv.lock").write_text(uv_lock.read_text(encoding="utf-8"), encoding="utf-8")

    npm_before = _run("cache-key", "npm-root", repo_root=fake_repo).stdout.strip()
    (fake_repo / "uv.lock").write_text(
        uv_lock.read_text(encoding="utf-8") + "\n# changed\n", encoding="utf-8"
    )
    npm_after = _run("cache-key", "npm-root", repo_root=fake_repo).stdout.strip()
    assert npm_before == npm_after


def test_docker_mcp_key_changes_when_dockerfile_changes(tmp_path: Path) -> None:
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    (fake_repo / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    (fake_repo / "pyproject.toml").write_text(
        (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (fake_repo / "uv.lock").write_text(
        (REPO_ROOT / "uv.lock").read_text(encoding="utf-8"), encoding="utf-8"
    )

    baseline = _run("cache-key", "docker-mcp", repo_root=fake_repo).stdout.strip()
    (fake_repo / "Dockerfile").write_text(dockerfile + "\n# changed\n", encoding="utf-8")
    changed = _run("cache-key", "docker-mcp", repo_root=fake_repo).stdout.strip()
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


def test_cache_paths_docker_mcp_empty() -> None:
    result = _run("cache-paths", "docker-mcp")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_cache_paths_vercel_cli_includes_npm_global_dirs() -> None:
    result = _run("cache-paths", "vercel-cli")
    assert result.returncode == 0
    paths = result.stdout.strip().splitlines()
    assert any(path.endswith(".npm") or "/.npm" in path for path in paths)

    npm_root = subprocess.run(
        ["npm", "root", "-g"],
        capture_output=True,
        text=True,
        check=False,
    )
    if npm_root.returncode == 0:
        assert npm_root.stdout.strip() in paths

    npm_prefix = subprocess.run(
        ["npm", "prefix", "-g"],
        capture_output=True,
        text=True,
        check=False,
    )
    if npm_prefix.returncode == 0:
        assert f"{npm_prefix.stdout.strip()}/bin" in paths


def test_restore_vercel_cli_hits_with_pinned_binary(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    vercel = fake_bin / "vercel"
    vercel.write_text("#!/usr/bin/env bash\necho 'Vercel CLI 58.4.4'\n", encoding="utf-8")
    vercel.chmod(0o755)

    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    env["DEPENDENCY_CACHE_ROOT"] = str(fake_repo)
    result = subprocess.run(
        ["/usr/bin/bash", str(CACHE_SCRIPT), "restore", "vercel-cli"],
        cwd=fake_repo,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _job_block(job_name: str) -> str:
    content = _read(CI_WORKFLOW)
    match = re.search(
        rf"^  {re.escape(job_name)}:\n(.*?)(?=^  \w|\Z)",
        content,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"job not found: {job_name}"
    return match.group(0)


def _assert_ci_deps_group(block: str, group: str) -> None:
    assert "uses: ./.github/actions/ci-deps" in block
    assert f"group: {group}" in block


def test_ci_deps_action_structure() -> None:
    content = _read(CI_DEPS_ACTION)
    assert "uses: actions/cache/restore@v4" in content
    assert "uses: actions/cache/save@v4" in content
    assert "dependency-cache.sh install" in content
    assert "has_paths == 'true' && steps.cache.outputs.cache-hit == 'true'" in content


def test_ci_workflow_safety_ci_deps_groups() -> None:
    block = _job_block("safety")
    _assert_ci_deps_group(block, "npm-root")
    _assert_ci_deps_group(block, "python-hooks")


def test_ci_workflow_verify_ci_deps_groups() -> None:
    block = _job_block("verify")
    _assert_ci_deps_group(block, "python-dev")
    _assert_ci_deps_group(block, "npm-root")


def test_ci_workflow_deploy_ci_deps_groups() -> None:
    block = _job_block("deploy")
    _assert_ci_deps_group(block, "python-hooks")
    _assert_ci_deps_group(block, "vercel-cli")


def test_ci_workflow_mcp_image_docker_cache_key() -> None:
    block = _job_block("mcp-image")
    assert "dependency-cache.sh cache-key docker-mcp" in block
    assert "cache-from: type=gha" in block
    assert "steps.docker_cache.outputs.key" in block
