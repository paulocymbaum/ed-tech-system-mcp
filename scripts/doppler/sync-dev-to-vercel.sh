#!/usr/bin/env bash
# Push runtime secrets from Doppler dev to Vercel production environment.
#
# At this stage dev is the single source of truth for app secrets (local + Vercel).
# Deploy credentials (VERCEL_*) still come from Doppler github_ci.
#
# Preflight: validates every key before writing anything to Vercel (no partial sync).
set -euo pipefail

PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
CONFIG="${DOPPLER_CONFIG:-dev}"
VERCEL_CREDENTIALS_CONFIG="${VERCEL_CREDENTIALS_CONFIG:-github_ci}"
VERCEL_ENV="${VERCEL_ENV:-production}"

VERCEL_CREDENTIAL_KEYS=(VERCEL_TOKEN VERCEL_ORG_ID VERCEL_PROJECT_ID)

# Required in Doppler dev (must be non-empty).
REQUIRED_DEV_KEYS=(
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
)

# Optional in dev — script applies defaults when missing or empty.
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
)

declare -A RUNTIME_DEFAULTS=(
  [LLM_MODEL]="llama-3.3-70b-versatile"
  [LLM_TEMPERATURE]="0"
  [LOG_LEVEL]="INFO"
  [EXTERNAL_REQUEST_LIMIT_PER_MINUTE]="60"
  [MCP_TRANSPORT]="streamable-http"
  [MCP_STATELESS_HTTP]="true"
  [VECTOR_STORE_BACKEND]="supabase"
)

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found." >&2
  exit 1
fi

if ! command -v vercel >/dev/null 2>&1; then
  echo "ERROR: vercel CLI not found. Run: npm install --global vercel" >&2
  exit 1
fi

if ! doppler me >/dev/null 2>&1; then
  echo "ERROR: Not authenticated. Run: doppler login" >&2
  exit 1
fi

declare -A RUNTIME_VALUES=()
declare -A VERCEL_CREDENTIALS=()

for key in "${VERCEL_CREDENTIAL_KEYS[@]}"; do
  if ! value="$(doppler secrets get "$key" --project "$PROJECT" --config "$VERCEL_CREDENTIALS_CONFIG" --plain 2>/dev/null)"; then
    echo "ERROR: Missing Doppler secret $key in $PROJECT / $VERCEL_CREDENTIALS_CONFIG" >&2
    exit 1
  fi
  if [[ -z "$value" ]]; then
    echo "ERROR: $key is empty in Doppler $VERCEL_CREDENTIALS_CONFIG" >&2
    exit 1
  fi
  VERCEL_CREDENTIALS["$key"]="$value"
done

for key in "${REQUIRED_DEV_KEYS[@]}"; do
  if ! value="$(doppler secrets get "$key" --project "$PROJECT" --config "$CONFIG" --plain 2>/dev/null)"; then
    echo "ERROR: Missing required secret $key in $PROJECT / $CONFIG" >&2
    echo "  Fill secrets in Doppler dev (dashboard or upload-local-env.sh), then retry." >&2
    exit 1
  fi
  if [[ -z "$value" ]]; then
    echo "ERROR: $key is empty in Doppler $CONFIG" >&2
    echo "  Fill secrets in Doppler dev (dashboard or upload-local-env.sh), then retry." >&2
    exit 1
  fi
  RUNTIME_VALUES["$key"]="$value"
done

for key in "${OPTIONAL_RUNTIME_KEYS[@]}"; do
  value="$(doppler secrets get "$key" --project "$PROJECT" --config "$CONFIG" --plain 2>/dev/null || true)"
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

# Vercel always runs with production semantics regardless of dev APP_ENV.
RUNTIME_VALUES["APP_ENV"]="production"

export VERCEL_TOKEN="${VERCEL_CREDENTIALS[VERCEL_TOKEN]}"
export VERCEL_ORG_ID="${VERCEL_CREDENTIALS[VERCEL_ORG_ID]}"
export VERCEL_PROJECT_ID="${VERCEL_CREDENTIALS[VERCEL_PROJECT_ID]}"

echo "→ Preflight OK — syncing from Doppler $PROJECT / $CONFIG to Vercel $VERCEL_ENV"

SYNC_KEYS=(APP_ENV "${REQUIRED_DEV_KEYS[@]}")
for key in "${OPTIONAL_RUNTIME_KEYS[@]}"; do
  if [[ -n "${RUNTIME_VALUES[$key]:-}" ]]; then
    SYNC_KEYS+=("$key")
  fi
done

for key in "${SYNC_KEYS[@]}"; do
  printf '%s' "${RUNTIME_VALUES[$key]}" | vercel env add "$key" "$VERCEL_ENV" --force --token="$VERCEL_TOKEN" >/dev/null
  echo "✓ Vercel env $key updated for $VERCEL_ENV (value not shown)"
done

echo "✓ Runtime secrets synced to Vercel ($VERCEL_ENV) from Doppler $PROJECT / $CONFIG"
echo "  Source of truth at this stage: dev only (see scripts/doppler/README.md)"
echo "  Re-deploy after sync: vercel deploy --prod --token=\"\$VERCEL_TOKEN\""
