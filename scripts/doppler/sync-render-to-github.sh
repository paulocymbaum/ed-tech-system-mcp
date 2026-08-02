#!/usr/bin/env bash
# Push RENDER_* secrets from Doppler github_ci to GitHub Actions.
set -euo pipefail

PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
CONFIG="${DOPPLER_CONFIG:-github_ci}"
REPO="${GITHUB_REPO:-paulocymbaum/ed-tech-system-mcp}"

RENDER_KEYS=(RENDER_DEPLOY_HOOK_URL RENDER_SERVICE_URL)

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

for key in "${RENDER_KEYS[@]}"; do
  if ! value="$(doppler secrets get "$key" --project "$PROJECT" --config "$CONFIG" --plain 2>/dev/null)"; then
    echo "ERROR: Missing Doppler secret $key in $PROJECT / $CONFIG" >&2
    exit 1
  fi
  if [[ -z "$value" ]]; then
    echo "ERROR: $key is empty in Doppler $CONFIG" >&2
    exit 1
  fi
  printf '%s' "$value" | gh secret set "$key" --repo "$REPO"
  echo "✓ GitHub secret $key updated (value not shown)"
done

echo "✓ Render secrets synced to GitHub repo $REPO from Doppler $CONFIG"
