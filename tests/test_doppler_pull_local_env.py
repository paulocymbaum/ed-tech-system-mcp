"""Contract tests for scripts/doppler/pull-local-env.sh."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PULL_SCRIPT = REPO_ROOT / "scripts/doppler/pull-local-env.sh"


def _run_pull_script(
    tmp_path: Path,
    *,
    doppler_script: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    run_env = os.environ.copy()
    # Isolate doppler but keep coreutils for dirname/mktemp in the script.
    run_env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    if env:
        run_env.update(env)

    if doppler_script is not None:
        doppler = fake_bin / "doppler"
        doppler.write_text(doppler_script, encoding="utf-8")
        doppler.chmod(0o755)

    return subprocess.run(
        ["/usr/bin/bash", str(PULL_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=run_env,
    )


def test_pull_script_requires_doppler_cli(tmp_path: Path) -> None:
    result = _run_pull_script(tmp_path)
    assert result.returncode == 1
    assert "doppler CLI not found" in result.stderr


def test_pull_script_requires_doppler_auth(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 1; fi
exit 0
"""
    result = _run_pull_script(tmp_path, doppler_script=doppler)
    assert result.returncode == 1
    assert "Not authenticated" in result.stderr


def test_pull_script_refuses_overwrite_without_force(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
exit 1
"""
    env_file = tmp_path / ".env"
    env_file.write_text("EXISTING=1\n", encoding="utf-8")
    result = _run_pull_script(
        tmp_path,
        doppler_script=doppler,
        env={"ENV_FILE": str(env_file), "FORCE": "0"},
    )
    assert result.returncode == 1
    assert "already exists" in result.stderr


def test_pull_script_writes_env_without_printing_secrets(tmp_path: Path) -> None:
    fake_secret = "super-secret-supabase-key-value"
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "download" ]]; then
  printf '%s\\n' 'SUPABASE_URL=https://example.supabase.co'
  printf '%s\\n' 'SUPABASE_SERVICE_ROLE_KEY=super-secret-supabase-key-value'
  exit 0
fi
exit 1
"""
    env_file = tmp_path / ".env"
    result = _run_pull_script(
        tmp_path,
        doppler_script=doppler,
        env={"ENV_FILE": str(env_file), "FORCE": "1"},
    )
    assert result.returncode == 0, result.stderr
    assert env_file.is_file()
    content = env_file.read_text(encoding="utf-8")
    assert "SUPABASE_URL=" in content
    assert fake_secret not in result.stdout
    assert fake_secret not in result.stderr
    assert "values not shown" in result.stdout
