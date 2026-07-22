#!/usr/bin/env bash
# Link this repo to Doppler without interactive prompts (works in IDE terminals).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
CONFIG="${DOPPLER_CONFIG:-dev}"

if ! command -v doppler >/dev/null 2>&1; then
  echo "ERROR: doppler CLI not found. Install: https://docs.doppler.com/docs/cli" >&2
  exit 1
fi

if ! doppler me >/dev/null 2>&1; then
  echo "ERROR: Not authenticated. Run: doppler login" >&2
  exit 1
fi

doppler setup \
  --project "$PROJECT" \
  --config "$CONFIG" \
  --no-interactive \
  --scope "$ROOT"

echo "✓ Linked $ROOT to Doppler project '$PROJECT' / config '$CONFIG'"
echo "  Run: doppler run -- uv run mcp-server"
