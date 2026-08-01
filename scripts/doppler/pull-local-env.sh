#!/usr/bin/env bash
# Write a gitignored repo-root .env from Doppler (dev by default).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
CONFIG="${DOPPLER_CONFIG:-dev}"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
FORCE="${FORCE:-0}"

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found." >&2
  exit 1
fi

if ! doppler me >/dev/null 2>&1; then
  echo "ERROR: Not authenticated. Run: doppler login" >&2
  exit 1
fi

if [[ -f "$ENV_FILE" && "$FORCE" != "1" ]]; then
  echo "ERROR: $ENV_FILE already exists. Set FORCE=1 to overwrite." >&2
  exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

if ! doppler secrets download \
  --project "$PROJECT" \
  --config "$CONFIG" \
  --format env \
  --no-file >"$tmp"; then
  echo "ERROR: doppler secrets download failed for $PROJECT / $CONFIG" >&2
  exit 1
fi

mv "$tmp" "$ENV_FILE"
trap - EXIT
chmod 600 "$ENV_FILE"

echo "✓ Wrote $ENV_FILE from Doppler $PROJECT / $CONFIG (values not shown)"
echo "  Machine overlays (Vercel CLI, etc.) can live in .env.local — loaded after .env."
