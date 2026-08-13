#!/usr/bin/env bash
# Sync Doppler dev runtime secrets to Render, then trigger a deploy and wait for it.
# Requires DOPPLER_TOKEN (+ DOPPLER_GITHUB_CI_TOKEN in CI) and RENDER_* in Doppler github_ci.
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$SCRIPT_ROOT"

# Free-tier Docker builds + boot can take several minutes; fail closed on update_failed.
RENDER_DEPLOY_TIMEOUT_SEC="${RENDER_DEPLOY_TIMEOUT_SEC:-900}"
RENDER_DEPLOY_POLL_SEC="${RENDER_DEPLOY_POLL_SEC:-15}"
RENDER_HEALTH_TIMEOUT_SEC="${RENDER_HEALTH_TIMEOUT_SEC:-180}"
RENDER_HEALTH_POLL_SEC="${RENDER_HEALTH_POLL_SEC:-10}"

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
  local deploy_id=""

  if [[ -n "$api_key" && -n "$service_id" ]]; then
    echo "→ Triggering Render deploy via API" >&2
    local response
    response="$(
      curl -fsS -X POST \
        -H "Authorization: Bearer ${api_key}" \
        -H "Content-Type: application/json" \
        -d '{}' \
        "https://api.render.com/v1/services/${service_id}/deploys"
    )"
    deploy_id="$(
      printf '%s' "$response" | python3 -c '
import json, sys
payload = json.load(sys.stdin)
if isinstance(payload, dict):
    print(payload.get("id") or payload.get("deploy", {}).get("id") or "")
elif isinstance(payload, list) and payload:
    item = payload[0]
    if isinstance(item, dict):
        print(item.get("id") or item.get("deploy", {}).get("id") or "")
'
    )"
    printf '%s' "$deploy_id"
    return 0
  fi

  if [[ -n "$hook_url" && "$hook_url" == https://api.render.com/deploy/* ]]; then
    echo "→ Triggering Render deploy hook" >&2
    curl -fsS -X POST "$hook_url" >/dev/null
    printf ''
    return 0
  fi

  return 1
}

latest_deploy_id() {
  local api_key="$1"
  local service_id="$2"
  curl -fsS \
    -H "Authorization: Bearer ${api_key}" \
    "https://api.render.com/v1/services/${service_id}/deploys?limit=1" \
    | python3 -c '
import json, sys
payload = json.load(sys.stdin)
if isinstance(payload, list) and payload:
    item = payload[0]
    if isinstance(item, dict):
        print(item.get("id") or item.get("deploy", {}).get("id") or "")
'
}

deploy_status() {
  local api_key="$1"
  local service_id="$2"
  local deploy_id="$3"
  curl -fsS \
    -H "Authorization: Bearer ${api_key}" \
    "https://api.render.com/v1/services/${service_id}/deploys/${deploy_id}" \
    | python3 -c '
import json, sys
payload = json.load(sys.stdin)
if isinstance(payload, dict):
    deploy = payload.get("deploy", payload)
    print(deploy.get("status") or "")
'
}

wait_for_deploy() {
  local api_key="$1"
  local service_id="$2"
  local deploy_id="$3"
  local deadline=$((SECONDS + RENDER_DEPLOY_TIMEOUT_SEC))
  local status=""

  echo "→ Waiting for Render deploy ${deploy_id} (timeout ${RENDER_DEPLOY_TIMEOUT_SEC}s)"
  while (( SECONDS < deadline )); do
    status="$(deploy_status "$api_key" "$service_id" "$deploy_id" || true)"
    case "$status" in
      live)
        echo "✓ Render deploy is live"
        return 0
        ;;
      update_failed|build_failed|canceled|deactivated|pre_deploy_failed)
        echo "ERROR: Render deploy ended with status=${status}" >&2
        return 1
        ;;
      *)
        echo "  status=${status:-unknown}; sleeping ${RENDER_DEPLOY_POLL_SEC}s"
        sleep "$RENDER_DEPLOY_POLL_SEC"
        ;;
    esac
  done

  echo "ERROR: Timed out waiting for Render deploy (last status=${status:-unknown})" >&2
  return 1
}

wait_for_health() {
  local service_url="$1"
  local health_url="${service_url%/}/health"
  local deadline=$((SECONDS + RENDER_HEALTH_TIMEOUT_SEC))

  echo "→ Waiting for ${health_url} (timeout ${RENDER_HEALTH_TIMEOUT_SEC}s)"
  while (( SECONDS < deadline )); do
    if curl -fsS --max-time 15 "$health_url" >/dev/null; then
      echo "✓ Health probe succeeded"
      return 0
    fi
    echo "  /health not ready; sleeping ${RENDER_HEALTH_POLL_SEC}s"
    sleep "$RENDER_HEALTH_POLL_SEC"
  done

  echo "ERROR: Timed out waiting for /health" >&2
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

deploy_id=""
if ! deploy_id="$(trigger_render_deploy "$hook_url" "$api_key" "$service_id")"; then
  echo "ERROR: Render deploy trigger failed" >&2
  record_deploy_failure
  exit 1
fi

if [[ -z "$deploy_id" && -n "$api_key" && -n "$service_id" ]]; then
  sleep 2
  deploy_id="$(latest_deploy_id "$api_key" "$service_id" || true)"
fi

if [[ -n "$deploy_id" && -n "$api_key" && -n "$service_id" ]]; then
  if ! wait_for_deploy "$api_key" "$service_id" "$deploy_id"; then
    record_deploy_failure
    exit 1
  fi
else
  echo "WARNING: Could not resolve deploy id; skipping deploy status wait"
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
  if ! wait_for_health "$service_url"; then
    record_deploy_failure
    exit 1
  fi
  echo "Render deploy succeeded; service URL ${service_url}"
else
  echo "Render deploy triggered (set RENDER_SERVICE_URL in Doppler $DOPPLER_GITHUB_CI_CONFIG for health probe URL)"
fi
