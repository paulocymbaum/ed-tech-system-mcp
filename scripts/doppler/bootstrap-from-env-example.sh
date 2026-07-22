#!/usr/bin/env bash
# Upload placeholder secrets to Doppler configs (dev, github_ci, stg, prd).
# Requires: doppler CLI authenticated (`doppler login`) or DOPPLER_TOKEN set.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found. Install: https://docs.doppler.com/docs/cli" >&2
  exit 1
fi

if ! doppler me >/dev/null 2>&1; then
  echo "ERROR: Not authenticated. Run: doppler login" >&2
  echo "       Or export DOPPLER_TOKEN with a personal or service token." >&2
  exit 1
fi

if ! doppler projects get "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: Doppler project '$PROJECT' not found. Create it in the dashboard or check DOPPLER_PROJECT." >&2
  exit 1
fi

ensure_github_ci_config() {
  if doppler configs get github_ci --project "$PROJECT" >/dev/null 2>&1; then
    return 0
  fi

  if ! doppler environments get github --project "$PROJECT" >/dev/null 2>&1; then
    echo "→ Creating Doppler environment: GitHub (github)"
    doppler environments create "GitHub" github -p "$PROJECT" --silent
  fi

  echo "→ Creating Doppler config: github_ci (CI / GitHub Actions sync)"
  doppler configs create github_ci --environment github -p "$PROJECT" --silent
}

render_env_file() {
  local app_env="$1"
  cat <<EOF
APP_ENV=${app_env}
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
TAVILY_API_KEY=
YOUTUBE_API_KEY=
GROQ_API_KEY=
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0
LOG_LEVEL=INFO
EOF
}

upload_config() {
  local config="$1"
  local app_env="$2"
  local env_file

  if ! doppler configs get "$config" --project "$PROJECT" >/dev/null 2>&1; then
    echo "ERROR: Doppler config '$config' not found in project '$PROJECT'." >&2
    exit 1
  fi

  env_file="$(mktemp)"
  trap 'rm -f "$env_file"' RETURN
  render_env_file "$app_env" >"$env_file"

  echo "→ Uploading placeholders to $PROJECT / $config"
  doppler secrets upload "$env_file" --project "$PROJECT" --config "$config" --silent
}

ensure_github_ci_config

upload_config dev development
upload_config github_ci ci
upload_config stg staging
upload_config prd production

bash "$ROOT/scripts/doppler/setup-local.sh"

echo "✓ Doppler bootstrap complete for project '$PROJECT' (dev, github_ci, stg, prd)"
echo "  Fill real values in the Doppler dashboard, then enable GitHub sync for github_ci."
