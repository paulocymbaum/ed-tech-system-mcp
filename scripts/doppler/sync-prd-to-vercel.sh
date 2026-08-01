#!/usr/bin/env bash
# Push runtime secrets from Doppler prd to Vercel production environment.
# Deploy credentials (VERCEL_*) are read from Doppler github_ci (no local `vercel link` needed).
set -euo pipefail

PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
CONFIG="${DOPPLER_CONFIG:-prd}"
VERCEL_CREDENTIALS_CONFIG="${VERCEL_CREDENTIALS_CONFIG:-github_ci}"
VERCEL_ENV="${VERCEL_ENV:-production}"

VERCEL_CREDENTIAL_KEYS=(VERCEL_TOKEN VERCEL_ORG_ID VERCEL_PROJECT_ID)

RUNTIME_KEYS=(
  APP_ENV
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
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

for key in "${VERCEL_CREDENTIAL_KEYS[@]}"; do
  if ! value="$(doppler secrets get "$key" --project "$PROJECT" --config "$VERCEL_CREDENTIALS_CONFIG" --plain 2>/dev/null)"; then
    echo "ERROR: Missing Doppler secret $key in $PROJECT / $VERCEL_CREDENTIALS_CONFIG" >&2
    echo "  Fill VERCEL_* in Doppler, or run: doppler run -- npx vercel link --yes" >&2
    exit 1
  fi
  if [[ -z "$value" ]]; then
    echo "ERROR: $key is empty in Doppler $VERCEL_CREDENTIALS_CONFIG" >&2
    exit 1
  fi
  printf -v "$key" '%s' "$value"
  export "$key"
done

for key in "${RUNTIME_KEYS[@]}"; do
  if ! value="$(doppler secrets get "$key" --project "$PROJECT" --config "$CONFIG" --plain 2>/dev/null)"; then
    echo "ERROR: Missing Doppler secret $key in $PROJECT / $CONFIG" >&2
    exit 1
  fi
  if [[ -z "$value" ]]; then
    echo "ERROR: $key is empty in Doppler $CONFIG" >&2
    exit 1
  fi
  printf '%s' "$value" | vercel env add "$key" "$VERCEL_ENV" --force --token="$VERCEL_TOKEN" >/dev/null
  echo "✓ Vercel env $key updated for $VERCEL_ENV (value not shown)"
done

echo "✓ Runtime secrets synced to Vercel ($VERCEL_ENV) from Doppler $PROJECT / $CONFIG"
echo "  Re-deploy after sync: vercel deploy --prod --token=\"\$VERCEL_TOKEN\""
