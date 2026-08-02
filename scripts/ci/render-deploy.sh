#!/usr/bin/env bash
# Sync Doppler dev runtime secrets to Render, then trigger a deploy.
# Requires DOPPLER_TOKEN (+ DOPPLER_GITHUB_CI_TOKEN in CI) and RENDER_* in Doppler github_ci.
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_ROOT"

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl not found." >&2
  exit 1
fi

if [[ -z "${DOPPLER_TOKEN:-}" ]] && ! doppler me >/dev/null 2>&1; then
  echo "ERROR: Not authenticated to Doppler. Set DOPPLER_TOKEN or run doppler login." >&2
  exit 1
fi

# shellcheck source=../doppler/doppler-ci-auth.sh
source "$(dirname "${BASH_SOURCE[0]}")/../doppler/doppler-ci-auth.sh"

get_github_ci_secret() {
  doppler_get_github_ci_secret "$1"
}

optional_github_ci_secret() {
  local key="$1"
  get_github_ci_secret "$key" 2>/dev/null || true
}

record_deploy_failure() {
  if [[ -x "$SCRIPT_ROOT/.venv/bin/python" ]]; then
    uv run python scripts/status/record_incident.py incident deployFailure \
      --summary "Render production deploy failed."
    uv run python scripts/status/build_manifest.py
  fi
}

trigger_render_deploy() {
  local hook_url="$1"
  local api_key="$2"
  local service_id="$3"

  if [[ -n "$hook_url" && "$hook_url" == https://api.render.com/deploy/* ]]; then
    echo "→ Triggering Render deploy hook"
    curl -fsS -X POST "$hook_url"
    return 0
  fi

  if [[ -n "$api_key" && -n "$service_id" ]]; then
    echo "→ Triggering Render deploy via API"
    curl -fsS -X POST \
      -H "Authorization: Bearer ${api_key}" \
      -H "Content-Type: application/json" \
      -d '{}' \
      "https://api.render.com/v1/services/${service_id}/deploys" >/dev/null
    return 0
  fi

  return 1
}

echo "→ Syncing runtime secrets from Doppler dev to Render"
bash scripts/doppler/sync-dev-to-render.sh

hook_url="$(optional_github_ci_secret RENDER_DEPLOY_HOOK_URL)"
api_key="$(optional_github_ci_secret RENDER_API_KEY)"
service_id="$(optional_github_ci_secret RENDER_SERVICE_ID)"

if [[ -z "$hook_url" && ( -z "$api_key" || -z "$service_id" ) ]]; then
  echo "No Render deploy trigger configured in Doppler $DOPPLER_GITHUB_CI_CONFIG; skipping deploy"
  exit 0
fi

if ! trigger_render_deploy "$hook_url" "$api_key" "$service_id"; then
  echo "ERROR: Render deploy trigger failed" >&2
  record_deploy_failure
  exit 1
fi

service_url="$(optional_github_ci_secret RENDER_SERVICE_URL)"
if [[ -z "$service_url" && -n "$service_id" && -n "$api_key" ]]; then
  service_url="$(
    curl -fsS \
      -H "Authorization: Bearer ${api_key}" \
      "https://api.render.com/v1/services/${service_id}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("serviceDetails",{}).get("url",""))'
  )"
fi

if [[ -n "$service_url" ]]; then
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "url=${service_url}" >> "$GITHUB_OUTPUT"
  fi
  echo "Triggered Render deploy; service URL ${service_url}"
else
  echo "Triggered Render deploy (set RENDER_SERVICE_URL in Doppler $DOPPLER_GITHUB_CI_CONFIG for health probe URL)"
fi
