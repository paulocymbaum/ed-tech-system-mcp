#!/usr/bin/env bash
# Sync Doppler dev runtime secrets to Render, then trigger the deploy hook.
# Requires DOPPLER_TOKEN (or doppler login) and RENDER_* in Doppler github_ci.
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_ROOT"

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found." >&2
  exit 1
fi

if ! doppler me >/dev/null 2>&1; then
  echo "ERROR: Not authenticated to Doppler. Set DOPPLER_TOKEN or run doppler login." >&2
  exit 1
fi

PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
GITHUB_CI_CONFIG="${DOPPLER_GITHUB_CI_CONFIG:-github_ci}"

get_github_ci_secret() {
  local key="$1"
  doppler secrets get "$key" --project "$PROJECT" --config "$GITHUB_CI_CONFIG" --plain
}

optional_github_ci_secret() {
  local key="$1"
  get_github_ci_secret "$key" 2>/dev/null || true
}

echo "→ Syncing runtime secrets from Doppler dev to Render"
bash scripts/doppler/sync-dev-to-render.sh

hook_url="$(get_github_ci_secret RENDER_DEPLOY_HOOK_URL)"
if [[ -z "$hook_url" ]]; then
  echo "RENDER_DEPLOY_HOOK_URL not configured in Doppler $GITHUB_CI_CONFIG; skipping deploy hook"
  exit 0
fi

echo "→ Triggering Render deploy hook"
if ! curl -fsS -X POST "$hook_url"; then
  echo "ERROR: Render deploy hook request failed" >&2
  if [[ -x "$SCRIPT_ROOT/.venv/bin/python" ]]; then
    uv run python scripts/status/record_incident.py incident deployFailure \
      --summary "Render production deploy failed."
    uv run python scripts/status/build_manifest.py
  fi
  exit 1
fi

service_url="$(optional_github_ci_secret RENDER_SERVICE_URL)"
if [[ -n "$service_url" ]]; then
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "url=${service_url}" >> "$GITHUB_OUTPUT"
  fi
  echo "Triggered Render deploy; service URL ${service_url}"
else
  echo "Triggered Render deploy (set RENDER_SERVICE_URL in Doppler $GITHUB_CI_CONFIG for health probe URL)"
fi
