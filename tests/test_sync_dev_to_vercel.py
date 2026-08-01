"""Contract tests for scripts/doppler/sync-dev-to-vercel.sh."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC_DEV = REPO_ROOT / "scripts/doppler/sync-dev-to-vercel.sh"
SYNC_PRD = REPO_ROOT / "scripts/doppler/sync-prd-to-vercel.sh"
README = REPO_ROOT / "scripts/doppler/README.md"


def _run_sync(
    tmp_path: Path,
    *,
    doppler_script: str,
    vercel_script: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    run_env = os.environ.copy()
    run_env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    if env:
        run_env.update(env)

    doppler = fake_bin / "doppler"
    doppler.write_text(doppler_script, encoding="utf-8")
    doppler.chmod(0o755)

    if vercel_script is not None:
        vercel = fake_bin / "vercel"
        vercel.write_text(vercel_script, encoding="utf-8")
        vercel.chmod(0o755)

    return subprocess.run(
        ["/usr/bin/bash", str(SYNC_DEV)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=run_env,
    )


def test_sync_dev_script_uses_dev_config_by_default() -> None:
    content = SYNC_DEV.read_text(encoding="utf-8")
    assert 'CONFIG="${DOPPLER_CONFIG:-dev}"' in content
    assert "Preflight" in content
    assert "REQUIRED_DEV_KEYS" in content


def test_sync_prd_wrapper_delegates_to_dev() -> None:
    content = SYNC_PRD.read_text(encoding="utf-8")
    assert "sync-dev-to-vercel.sh" in content
    assert "deprecated" in content.lower()


def test_doppler_readme_documents_dev_as_source() -> None:
    content = README.read_text(encoding="utf-8")
    assert "dev" in content
    assert "single source of truth" in content.lower()
    assert "sync-dev-to-vercel.sh" in content


def test_sync_fails_when_supabase_missing_in_dev(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then
  key="$3"
  case "$key" in
    VERCEL_TOKEN|VERCEL_ORG_ID|VERCEL_PROJECT_ID) printf 'x' ;;
    SUPABASE_URL) exit 1 ;;
    *) printf '' ;;
  esac
  exit 0
fi
exit 1
"""
    vercel = "#!/usr/bin/bash\nexit 0\n"
    result = _run_sync(tmp_path, doppler_script=doppler, vercel_script=vercel)
    assert result.returncode == 1
    assert "SUPABASE_URL" in result.stderr
    assert "dev" in result.stderr.lower()


def test_sync_preflight_before_vercel_writes(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then
  key="$3"
  case "$key" in
    VERCEL_TOKEN|VERCEL_ORG_ID|VERCEL_PROJECT_ID) printf 'token' ;;
    SUPABASE_URL) printf 'https://example.supabase.co' ;;
    SUPABASE_SERVICE_ROLE_KEY) exit 1 ;;
    *) printf '' ;;
  esac
  exit 0
fi
exit 1
"""
    vercel = "#!/usr/bin/bash\necho 'should not run' >&2\nexit 0\n"
    result = _run_sync(tmp_path, doppler_script=doppler, vercel_script=vercel)
    assert result.returncode == 1
    assert "should not run" not in result.stderr


def test_sync_skips_empty_optional_keys_without_defaults(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then
  key="$3"
  case "$key" in
    VERCEL_TOKEN|VERCEL_ORG_ID|VERCEL_PROJECT_ID) printf 'token' ;;
    SUPABASE_URL) printf 'https://example.supabase.co' ;;
    SUPABASE_SERVICE_ROLE_KEY) printf 'service-role-key' ;;
    TAVILY_API_KEY|YOUTUBE_API_KEY|GROQ_API_KEY) printf '' ;;
    *) printf '' ;;
  esac
  exit 0
fi
exit 1
"""
    vercel = """#!/usr/bin/bash
if [[ "$1" == "env" && "$2" == "add" ]]; then
  echo "$3" >> /tmp/vercel-env-keys.log
fi
exit 0
"""
    log = tmp_path / "vercel-env-keys.log"
    result = _run_sync(
        tmp_path,
        doppler_script=doppler,
        vercel_script=vercel.replace("/tmp/vercel-env-keys.log", str(log)),
    )
    assert result.returncode == 0, result.stderr
    synced = log.read_text(encoding="utf-8").splitlines()
    assert "TAVILY_API_KEY" not in synced
    assert "APP_ENV" in synced


def test_sync_sets_app_env_production_on_vercel(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then
  key="$3"
  case "$key" in
    VERCEL_TOKEN|VERCEL_ORG_ID|VERCEL_PROJECT_ID) printf 'token' ;;
    SUPABASE_URL) printf 'https://example.supabase.co' ;;
    SUPABASE_SERVICE_ROLE_KEY) printf 'service-role-key' ;;
    TAVILY_API_KEY|YOUTUBE_API_KEY|GROQ_API_KEY) printf '' ;;
    *) printf '' ;;
  esac
  exit 0
fi
exit 1
"""
    vercel = """#!/usr/bin/bash
if [[ "$1" == "env" && "$2" == "add" ]]; then
  echo "$1 $2 $3 $4" >> /tmp/vercel-env-calls.log
fi
exit 0
"""
    log = tmp_path / "vercel-env-calls.log"
    result = _run_sync(
        tmp_path,
        doppler_script=doppler,
        vercel_script=vercel.replace("/tmp/vercel-env-calls.log", str(log)),
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8")
    assert "env add APP_ENV" in calls
