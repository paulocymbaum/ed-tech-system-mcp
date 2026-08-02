#!/usr/bin/env bash
# Create config-scoped Doppler service tokens and store them in GitHub Actions.
set -euo pipefail

PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
DEV_CONFIG="${DOPPLER_DEV_CONFIG:-dev}"
GITHUB_CI_CONFIG="${DOPPLER_GITHUB_CI_CONFIG:-github_ci}"
REPO="${GITHUB_REPO:-paulocymbaum/ed-tech-system-mcp}"
DEV_TOKEN_NAME="${DOPPLER_DEV_TOKEN_NAME:-github-actions-dev}"
GITHUB_CI_TOKEN_NAME="${DOPPLER_GITHUB_CI_TOKEN_NAME:-github-actions-github-ci}"

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI not found." >&2
  exit 1
fi

if ! doppler me >/dev/null 2>&1; then
  echo "ERROR: Not authenticated. Run: doppler login" >&2
  exit 1
fi

create_service_token() {
  local name="$1"
  local config="$2"
  doppler configs tokens create "$name" \
    --project "$PROJECT" \
    --config "$config" \
    --access read \
    --plain
}

echo "→ Creating Doppler service token for $PROJECT / $DEV_CONFIG"
dev_token="$(create_service_token "$DEV_TOKEN_NAME" "$DEV_CONFIG")"
printf '%s' "$dev_token" | gh secret set DOPPLER_TOKEN --repo "$REPO"
echo "✓ GitHub secret DOPPLER_TOKEN updated (dev config, value not shown)"

echo "→ Creating Doppler service token for $PROJECT / $GITHUB_CI_CONFIG"
github_ci_token="$(create_service_token "$GITHUB_CI_TOKEN_NAME" "$GITHUB_CI_CONFIG")"
printf '%s' "$github_ci_token" | gh secret set DOPPLER_GITHUB_CI_TOKEN --repo "$REPO"
echo "✓ GitHub secret DOPPLER_GITHUB_CI_TOKEN updated (github_ci config, value not shown)"

echo "✓ Doppler CI tokens synced to GitHub repo $REPO"
