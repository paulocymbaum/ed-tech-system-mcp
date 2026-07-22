#!/usr/bin/env bash
# Upload gitignored repo-root .env to a Doppler config (dev by default).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
CONFIG="${DOPPLER_CONFIG:-dev}"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found." >&2
  exit 1
fi

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found." >&2
  exit 1
fi

upload_file="$(mktemp)"
trap 'rm -f "$upload_file"' EXIT
grep -v '^DOPPLER_' "$ENV_FILE" | grep -v '^#' >"$upload_file"

echo "→ Uploading secrets from $ENV_FILE to $PROJECT / $CONFIG"
doppler secrets upload "$upload_file" --project "$PROJECT" --config "$CONFIG" --silent
echo "✓ Doppler upload complete"
