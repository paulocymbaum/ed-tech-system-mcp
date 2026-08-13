#!/usr/bin/env bash
# Push runtime secrets from Doppler dev to a Render Web Service.
#
# Preflight: validates every key before writing anything to Render (no partial sync).
# Requires: curl, doppler CLI, RENDER_API_KEY + RENDER_SERVICE_ID in Doppler github_ci.
set -euo pipefail

PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
CONFIG="${DOPPLER_CONFIG:-dev}"
RENDER_CREDENTIALS_CONFIG="${RENDER_CREDENTIALS_CONFIG:-github_ci}"

RENDER_CREDENTIAL_KEYS=(RENDER_API_KEY RENDER_SERVICE_ID)

REQUIRED_DEV_KEYS=(
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
)

OPTIONAL_RUNTIME_KEYS=(
  TAVILY_API_KEY
  YOUTUBE_API_KEY
  GROQ_API_KEY
  LLM_MODEL
  LLM_TEMPERATURE
  LOG_LEVEL
  EXTERNAL_REQUEST_LIMIT_PER_MINUTE
  MCP_TRANSPORT
  MCP_STATELESS_HTTP
  VECTOR_STORE_BACKEND
  EMBEDDING_CACHE_DIR
  EMBEDDING_WARM_ON_BOOT
  HF_HOME
  XDG_CACHE_HOME
  GROQ_MODEL_CATALOG_CACHE_PATH
)

declare -A RUNTIME_DEFAULTS=(
  [LLM_MODEL]="llama-3.3-70b-versatile"
  [LLM_TEMPERATURE]="0"
  [LOG_LEVEL]="INFO"
  [EXTERNAL_REQUEST_LIMIT_PER_MINUTE]="60"
  [MCP_TRANSPORT]="streamable-http"
  [MCP_STATELESS_HTTP]="true"
  [VECTOR_STORE_BACKEND]="supabase"
  [EMBEDDING_CACHE_DIR]="/app/model-cache/fastembed"
  [EMBEDDING_WARM_ON_BOOT]="false"
  [HF_HOME]="/tmp/hf"
  [XDG_CACHE_HOME]="/tmp"
  [GROQ_MODEL_CATALOG_CACHE_PATH]="/tmp/app-cache/groq_model_catalog.json"
)

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found." >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl not found." >&2
  exit 1
fi

if [[ -z "${DOPPLER_TOKEN:-}" ]] && ! doppler me >/dev/null 2>&1; then
  echo "ERROR: Not authenticated. Set DOPPLER_TOKEN or run doppler login." >&2
  exit 1
fi

# shellcheck source=doppler-ci-auth.sh
source "$(dirname "${BASH_SOURCE[0]}")/doppler-ci-auth.sh"

declare -A RUNTIME_VALUES=()
declare -A RENDER_CREDENTIALS=()

for key in "${RENDER_CREDENTIAL_KEYS[@]}"; do
  if ! value="$(doppler_get_github_ci_secret "$key" 2>/dev/null)"; then
    echo "ERROR: Missing Doppler secret $key in $PROJECT / $RENDER_CREDENTIALS_CONFIG" >&2
    exit 1
  fi
  if [[ -z "$value" ]]; then
    echo "ERROR: $key is empty in Doppler $RENDER_CREDENTIALS_CONFIG" >&2
    exit 1
  fi
  RENDER_CREDENTIALS["$key"]="$value"
done

for key in "${REQUIRED_DEV_KEYS[@]}"; do
  if ! value="$(doppler_get_dev_secret "$key" 2>/dev/null)"; then
    echo "ERROR: Missing required secret $key in $PROJECT / $CONFIG" >&2
    exit 1
  fi
  if [[ -z "$value" ]]; then
    echo "ERROR: $key is empty in Doppler $CONFIG" >&2
    exit 1
  fi
  RUNTIME_VALUES["$key"]="$value"
done

for key in "${OPTIONAL_RUNTIME_KEYS[@]}"; do
  value="$(doppler_get_dev_secret "$key" 2>/dev/null || true)"
  if [[ -z "$value" ]]; then
    default="${RUNTIME_DEFAULTS[$key]:-}"
    if [[ -z "$default" ]]; then
      echo "→ Skipping optional $key (empty in Doppler $CONFIG)"
      continue
    fi
    value="$default"
  fi
  RUNTIME_VALUES["$key"]="$value"
done

RUNTIME_VALUES["APP_ENV"]="production"

service_id="${RENDER_CREDENTIALS[RENDER_SERVICE_ID]}"
api_key="${RENDER_CREDENTIALS[RENDER_API_KEY]}"

echo "→ Preflight OK — syncing from Doppler $PROJECT / $CONFIG to Render service $service_id"

SYNC_KEYS=(APP_ENV "${REQUIRED_DEV_KEYS[@]}")
for key in "${OPTIONAL_RUNTIME_KEYS[@]}"; do
  if [[ -n "${RUNTIME_VALUES[$key]:-}" ]]; then
    SYNC_KEYS+=("$key")
  fi
done

for key in "${SYNC_KEYS[@]}"; do
  payload="$(printf '{"envVarKey":"%s","value":"%s"}' "$key" "${RUNTIME_VALUES[$key]}")"
  if ! curl -fsS -X PUT \
    -H "Authorization: Bearer ${api_key}" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "https://api.render.com/v1/services/${service_id}/env-vars/${key}" >/dev/null; then
    echo "ERROR: Failed to sync $key to Render" >&2
    exit 1
  fi
  echo "✓ Render env $key updated (value not shown)"
done

echo "✓ Runtime secrets synced to Render from Doppler $PROJECT / $CONFIG"
echo "  Trigger redeploy from the Render dashboard or deploy hook."
