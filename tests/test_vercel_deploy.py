"""Tests for Vercel deployment layer contracts (workflow, bootstrap, sync, gitignore)."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY_WORKFLOW = REPO_ROOT / ".github/workflows/deploy.yml"
VERCEL_JSON = REPO_ROOT / "vercel.json"
BOOTSTRAP_SCRIPT = REPO_ROOT / "scripts/doppler/bootstrap-from-env-example.sh"
SYNC_SCRIPT = REPO_ROOT / "scripts/doppler/sync-vercel-to-github.sh"
GITIGNORE = REPO_ROOT / ".gitignore"

VERCEL_SECRET_NAMES = ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _deploy_step_block(step_name: str) -> str:
    content = _read(DEPLOY_WORKFLOW)
    match = re.search(
        rf"- name: {re.escape(step_name)}\n(?:(?!- name: ).*\n)*",
        content,
        flags=re.MULTILINE,
    )
    assert match is not None, f"deploy step not found: {step_name}"
    return match.group(0)


def _render_env_template() -> str:
    content = _read(BOOTSTRAP_SCRIPT)
    match = re.search(
        r"render_env_file\(\) \{[^}]*cat <<EOF\n(.*?)EOF",
        content,
        flags=re.DOTALL,
    )
    assert match is not None, "render_env_file heredoc not found"
    return match.group(1)


def _run_sync_script(
    tmp_path: Path,
    *,
    doppler_script: str | None = None,
    gh_script: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    # Isolate PATH so host doppler/gh are not picked up during contract tests.
    run_env["PATH"] = str(fake_bin)

    if doppler_script is not None:
        doppler = fake_bin / "doppler"
        doppler.write_text(doppler_script, encoding="utf-8")
        doppler.chmod(0o755)

    if gh_script is not None:
        gh = fake_bin / "gh"
        gh.write_text(gh_script, encoding="utf-8")
        gh.chmod(0o755)

    return subprocess.run(
        ["/usr/bin/bash", str(SYNC_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=run_env,
    )


def test_T01_deploy_workflow_name() -> None:
    assert 'name: Deploy workflow UI' in _read(DEPLOY_WORKFLOW)


def test_T02_deploy_triggers_main_and_dispatch() -> None:
    content = _read(DEPLOY_WORKFLOW)
    on_block = content.split("concurrency:", maxsplit=1)[0]
    assert "workflow_dispatch:" in on_block
    assert "branches: [main]" in on_block or "branches:\n      - main" in on_block


def test_T03_deploy_concurrency_group() -> None:
    content = _read(DEPLOY_WORKFLOW)
    assert "group: vercel-${{ github.ref }}" in content
    assert "cancel-in-progress: true" in content


def test_T04_deploy_permissions_read_only() -> None:
    content = _read(DEPLOY_WORKFLOW)
    permissions = content.split("jobs:", maxsplit=1)[0]
    assert "contents: read" in permissions
    assert "contents: write" not in permissions


def test_T05_deploy_production_environment() -> None:
    content = _read(DEPLOY_WORKFLOW)
    assert "name: production" in content
    assert "url: ${{ steps.vercel.outputs.url }}" in content


def test_T06_deploy_node20_ui_build() -> None:
    content = _read(DEPLOY_WORKFLOW)
    assert 'node-version: "20"' in content
    build = _deploy_step_block("Build workflow UI")
    assert "working-directory: ui" in build
    assert "npm ci" in build
    assert "npm run build" in build


def test_T07_deploy_vite_api_base_var() -> None:
    build = _deploy_step_block("Build workflow UI")
    assert "VITE_API_BASE: ${{ vars.VITE_API_BASE || '' }}" in build


def test_T08_deploy_prebuilt_package_layout() -> None:
    package = _deploy_step_block("Package static output for Vercel")
    assert "mkdir -p .vercel/output/static" in package
    assert "cp -r ui/dist/. .vercel/output/static/" in package
    assert '.vercel/output/config.json' in package
    assert '"version": 3' in package
    assert '"handle": "filesystem"' in package
    assert '"dest": "/index.html"' in package


def test_T09_deploy_vercel_cli_pinned() -> None:
    install = _deploy_step_block("Install Vercel CLI")
    assert "vercel@58.4.4" in install
    assert "vercel@latest" not in install


def test_T10_deploy_uses_prebuilt_prod_flags() -> None:
    deploy = _deploy_step_block("Deploy to Vercel")
    assert "vercel deploy --prebuilt --prod --yes" in deploy


def test_T11_deploy_references_vercel_secrets() -> None:
    deploy = _deploy_step_block("Deploy to Vercel")
    for secret_name in VERCEL_SECRET_NAMES:
        assert f"${{{{ secrets.{secret_name} }}}}" in deploy


def test_T12_deploy_no_secret_echo() -> None:
    deploy = _deploy_step_block("Deploy to Vercel")
    run_block = deploy.split("run: |", maxsplit=1)[1]
    assert 'echo "$VERCEL_TOKEN"' not in run_block
    assert "echo $VERCEL_TOKEN" not in run_block
    assert 'echo "$VERCEL_ORG_ID"' not in run_block
    assert 'echo "$VERCEL_PROJECT_ID"' not in run_block


def test_T13_deploy_url_capture_hardened() -> None:
    deploy = _deploy_step_block("Deploy to Vercel")
    assert "deploy_out=$(mktemp)" in deploy
    assert "deploy_err=$(mktemp)" in deploy
    assert "grep -Eo 'https://[^[:space:]]+'" in deploy
    assert 'echo "url=$url" >> "$GITHUB_OUTPUT"' in deploy


def test_T20_bootstrap_vercel_placeholders_in_template() -> None:
    template = _render_env_template()
    for key in VERCEL_SECRET_NAMES:
        assert f"{key}=" in template


def test_T21_bootstrap_uploads_four_configs() -> None:
    content = _read(BOOTSTRAP_SCRIPT)
    for config in ("dev", "github_ci", "stg", "prd"):
        assert f"upload_config {config}" in content


def test_T30_vercel_json_valid() -> None:
    payload = json.loads(_read(VERCEL_JSON))
    assert isinstance(payload, dict)


def test_T31_vercel_output_directory_ui_dist() -> None:
    payload = json.loads(_read(VERCEL_JSON))
    assert payload["outputDirectory"] == "ui/dist"


def test_T32_vercel_spa_rewrite() -> None:
    payload = json.loads(_read(VERCEL_JSON))
    rewrites = payload["rewrites"]
    assert any(
        rewrite.get("source") == "/(.*)" and rewrite.get("destination") == "/index.html"
        for rewrite in rewrites
    )


def test_T33_vercel_build_commands_reference_ui() -> None:
    payload = json.loads(_read(VERCEL_JSON))
    assert "ui" in payload["buildCommand"]
    assert "ui" in payload["installCommand"]


def test_T40_sync_script_required_keys() -> None:
    content = _read(SYNC_SCRIPT)
    assert "VERCEL_KEYS=(VERCEL_TOKEN VERCEL_ORG_ID VERCEL_PROJECT_ID)" in content


def test_T41_sync_script_no_value_logging() -> None:
    content = _read(SYNC_SCRIPT)
    assert 'echo "$value"' not in content
    assert "echo $value" not in content
    assert 'printf "%s\n" "$value"' not in content


def test_T42_sync_script_requires_doppler_cli(tmp_path: Path) -> None:
    result = _run_sync_script(tmp_path)
    assert result.returncode == 1
    assert "doppler CLI not found" in result.stderr


def test_T43_sync_script_requires_gh_cli(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
exit 1
"""
    result = _run_sync_script(tmp_path, doppler_script=doppler)
    assert result.returncode == 1
    assert "gh CLI not found" in result.stderr


def test_T44_sync_script_missing_doppler_secret(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then exit 1; fi
exit 1
"""
    gh = "#!/usr/bin/bash\nexit 0\n"
    result = _run_sync_script(tmp_path, doppler_script=doppler, gh_script=gh)
    assert result.returncode == 1
    assert "Missing Doppler secret" in result.stderr


def test_T45_sync_script_empty_doppler_secret(tmp_path: Path) -> None:
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then
  exit 0
fi
exit 1
"""
    gh = "#!/usr/bin/bash\nexit 0\n"
    result = _run_sync_script(tmp_path, doppler_script=doppler, gh_script=gh)
    assert result.returncode == 1
    assert "is empty" in result.stderr


def test_T46_sync_script_success_without_printing_secrets(tmp_path: Path) -> None:
    fake_secret = "fake-vercel-token-value-12345"
    doppler = """#!/usr/bin/bash
if [[ "$1" == "me" ]]; then exit 0; fi
if [[ "$1" == "secrets" && "$2" == "get" ]]; then
  key="$3"
  case "$key" in
    VERCEL_TOKEN) printf '%s' 'fake-vercel-token-value-12345' ;;
    VERCEL_ORG_ID) printf '%s' 'org_fake_id' ;;
    VERCEL_PROJECT_ID) printf '%s' 'prj_fake_id' ;;
  esac
  exit 0
fi
exit 1
"""
    gh = """#!/usr/bin/bash
if [[ "$1" == "secret" && "$2" == "set" ]]; then
  cat > /dev/null
  exit 0
fi
exit 1
"""
    result = _run_sync_script(
        tmp_path,
        doppler_script=doppler,
        gh_script=gh,
        env={"GITHUB_REPO": "example/test-repo"},
    )
    assert result.returncode == 0, result.stderr
    assert fake_secret not in result.stdout
    assert fake_secret not in result.stderr
    assert "value not shown" in result.stdout


def test_T50_gitignore_vercel_pattern() -> None:
    lines = _read(GITIGNORE).splitlines()
    assert ".vercel/" in lines


def test_T51_vercel_directory_gitignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", "-q", ".vercel/"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_T52_ui_lib_sources_are_not_gitignored() -> None:
    """CI must ship ui/src/lib — a broad lib/ gitignore pattern broke Vercel builds."""
    for relative in (
        "ui/src/lib/traceAnalytics.ts",
        "ui/src/lib/ragBenchmarks.ts",
        "ui/src/lib/ragNodeGroups.ts",
    ):
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, f"{relative} must not be gitignored"
