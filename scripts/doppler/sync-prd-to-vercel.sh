#!/usr/bin/env bash
# Deprecated wrapper — use sync-dev-to-vercel.sh (dev is the secrets source for Vercel at this stage).
set -euo pipefail
echo "NOTE: sync-prd-to-vercel.sh is deprecated. Using Doppler dev → Vercel (see scripts/doppler/README.md)." >&2
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$ROOT/sync-dev-to-vercel.sh" "$@"
