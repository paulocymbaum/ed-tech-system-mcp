#!/usr/bin/env bash
# Push runtime secrets from Doppler prd to Vercel production environment.
# Deploy credentials (VERCEL_*) stay in Doppler github_ci → GitHub Actions only.
set -euo pipefail

PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
CONFIG="${DOPPLER_CONFIG:-prd}"
VERCEL_ENV="${VERCEL_ENV:-production}"

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

for key in "${RUNTIME_KEYS[@]}"; do
  if ! value="$(doppler secrets get "$key" --project "$PROJECT" --config "$CONFIG" --plain 2>/dev/null)"; then
    echo "ERROR: Missing Doppler secret $key in $PROJECT / $CONFIG" >&2
    exit 1
  fi
  if [[ -z "$value" ]]; then
    echo "ERROR: $key is empty in Doppler $CONFIG" >&2
    exit 1
  fi
  printf '%s' "$value" | vercel env add "$key" "$VERCEL_ENV" --force >/dev/null
  echo "✓ Vercel env $key updated for $VERCEL_ENV (value not shown)"
done

echo "✓ Runtime secrets synced to Vercel ($VERCEL_ENV) from Doppler $PROJECT / $CONFIG"
echo "  Re-deploy after sync: vercel deploy --prod"
