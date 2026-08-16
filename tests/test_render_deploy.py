"""Tests for Render deployment layer contracts."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"
RENDER_YAML = REPO_ROOT / "render.yaml"
RENDER_MD = REPO_ROOT / "RENDER.md"
BOOTSTRAP_SCRIPT = REPO_ROOT / "scripts/doppler/bootstrap-from-env-example.sh"
SYNC_SCRIPT = REPO_ROOT / "scripts/doppler/sync-render-to-github.sh"
RENDER_DEPLOY_SCRIPT = REPO_ROOT / "scripts/ci/render-deploy.sh"
GITIGNORE = REPO_ROOT / ".gitignore"

RENDER_SECRET_NAMES = ("RENDER_DEPLOY_HOOK_URL", "RENDER_SERVICE_URL")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _deploy_step_block(step_name: str) -> str:
    content = _read(CI_WORKFLOW)
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


def test_ci_deploy_job_targets_render() -> None:
    deploy_job = _read(CI_WORKFLOW).split("  deploy:", maxsplit=1)[1]
    assert "Deploy MCP to Render" in deploy_job
    assert "vercel deploy" not in deploy_job
    assert "dopplerhq/cli-action" in deploy_job
    assert "scripts/ci/render-deploy.sh" in deploy_job


def test_render_yaml_valid() -> None:
    import yaml

    payload = yaml.safe_load(_read(RENDER_YAML))
    assert payload["services"][0]["runtime"] == "docker"
    assert payload["services"][0]["healthCheckPath"] == "/health"


def test_render_yaml_sets_writable_embedding_cache_dir() -> None:
    import yaml

    payload = yaml.safe_load(_read(RENDER_YAML))
    env_vars = {
        item["key"]: item["value"]
        for item in payload["services"][0]["envVars"]
        if "value" in item
    }
    assert env_vars["EMBEDDING_CACHE_DIR"] == "/app/model-cache/fastembed"
    assert env_vars["EMBEDDING_WARM_ON_BOOT"] == "false"
    assert env_vars["RERANK_ENABLED"] == "false"
    assert env_vars["LOG_LEVEL"] == "INFO"
    assert env_vars["MCP_REQUIRE_INBOUND_TOKEN"] == "true"
    assert env_vars["MCP_REQUIRE_CALLER_JWT"] == "true"
    assert env_vars["MCP_ALLOWED_HOSTS"] == "ed-tech-system-mcp.onrender.com"
    assert env_vars["HF_HOME"] == "/tmp/hf"
    assert env_vars["XDG_CACHE_HOME"] == "/tmp"
    assert env_vars["GROQ_MODEL_CATALOG_CACHE_PATH"] == "/tmp/app-cache/groq_model_catalog.json"


def test_render_md_exists() -> None:
    assert RENDER_MD.is_file()
    assert "onrender.com" in _read(RENDER_MD)


def test_no_vercel_entrypoint_artifacts() -> None:
    assert not (REPO_ROOT / "vercel.json").exists()
    assert not (REPO_ROOT / "VERCEL.md").exists()
    assert not (REPO_ROOT / "src/mcp_server/vercel_app.py").exists()
    content = _read(REPO_ROOT / "pyproject.toml")
    assert "[tool.vercel]" not in content


def test_bootstrap_render_placeholders_in_template() -> None:
    template = _render_env_template()
    for key in ("RENDER_API_KEY", "RENDER_SERVICE_ID", "RENDER_DEPLOY_HOOK_URL"):
        assert f"{key}=" in template


def test_sync_script_required_keys() -> None:
    content = _read(SYNC_SCRIPT)
    assert "RENDER_KEYS=(RENDER_DEPLOY_HOOK_URL RENDER_SERVICE_URL)" in content


def test_render_deploy_script_contract() -> None:
    content = _read(RENDER_DEPLOY_SCRIPT)
    assert "sync-dev-to-render.sh" in content
    for secret_name in RENDER_SECRET_NAMES:
        assert secret_name in content
    assert "api.render.com/v1/services" in content
    assert "wait_for_deploy" in content
    assert "update_failed" in content
    assert "wait_for_health" in content
    assert "secrets.DOPPLER_TOKEN" not in content


def test_trigger_render_deploy_step() -> None:
    step = _deploy_step_block("Sync secrets and trigger Render deploy")
    assert "scripts/ci/render-deploy.sh" in step
    assert "DOPPLER_TOKEN" in step
    assert "DOPPLER_GITHUB_CI_TOKEN" in step


def test_gitignore_vercel_pattern() -> None:
    lines = _read(GITIGNORE).splitlines()
    assert ".vercel/" in lines
