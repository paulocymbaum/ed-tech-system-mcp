"""Contract tests for scripts/doppler/sync-dev-to-render.sh."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC_DEV = REPO_ROOT / "scripts/doppler/sync-dev-to-render.sh"
SYNC_PRD = REPO_ROOT / "scripts/doppler/sync-prd-to-render.sh"
README = REPO_ROOT / "scripts/doppler/README.md"


def _run_sync(
    tmp_path: Path,
    *,
    doppler_script: str,
    curl_script: str | None = None,
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

    if curl_script is not None:
        curl = fake_bin / "curl"
        curl.write_text(curl_script, encoding="utf-8")
        curl.chmod(0o755)

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


def test_sync_dev_script_includes_writable_cache_defaults() -> None:
    content = SYNC_DEV.read_text(encoding="utf-8")
    assert "EMBEDDING_CACHE_DIR" in content
    assert "EMBEDDING_WARM_ON_BOOT" in content
    assert "HF_HOME" in content
    assert "GROQ_MODEL_CATALOG_CACHE_PATH" in content
    assert '[EMBEDDING_CACHE_DIR]="/app/model-cache/fastembed"' in content
    assert '[EMBEDDING_WARM_ON_BOOT]="true"' in content
    assert '[HF_HOME]="/tmp/hf"' in content
    assert '[GROQ_MODEL_CATALOG_CACHE_PATH]="/tmp/app-cache/groq_model_catalog.json"' in content


def test_sync_prd_wrapper_delegates_to_dev() -> None:
    content = SYNC_PRD.read_text(encoding="utf-8")
    assert "sync-dev-to-render.sh" in content
    assert "deprecated" in content.lower()


def test_doppler_readme_documents_render_sync() -> None:
    content = README.read_text(encoding="utf-8")
    assert "sync-dev-to-render.sh" in content
    assert "Render" in content


def test_sync_fails_when_supabase_missing_in_dev(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then
  key="$3"
  case "$key" in
    RENDER_API_KEY|RENDER_SERVICE_ID) printf 'x' ;;
    SUPABASE_URL) exit 1 ;;
    *) printf '' ;;
  esac
  exit 0
fi
exit 1
"""
    curl = "#!/usr/bin/bash\nexit 0\n"
    result = _run_sync(tmp_path, doppler_script=doppler, curl_script=curl)
    assert result.returncode == 1
    assert "SUPABASE_URL" in result.stderr


def test_sync_preflight_before_render_writes(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then
  key="$3"
  case "$key" in
    RENDER_API_KEY|RENDER_SERVICE_ID) printf 'token' ;;
    SUPABASE_URL) printf 'https://example.supabase.co' ;;
    SUPABASE_SERVICE_ROLE_KEY) exit 1 ;;
    *) printf '' ;;
  esac
  exit 0
fi
exit 1
"""
    curl = "#!/usr/bin/bash\necho 'should not run' >&2\nexit 0\n"
    result = _run_sync(tmp_path, doppler_script=doppler, curl_script=curl)
    assert result.returncode == 1
    assert "should not run" not in result.stderr
