#!/usr/bin/env bash
# Deprecated wrapper — use sync-dev-to-render.sh (dev is the secrets source for Render at this stage).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "NOTE: sync-prd-to-render.sh is deprecated. Using Doppler dev → Render (see scripts/doppler/README.md)." >&2
# shellcheck source=/dev/null
exec "$ROOT/sync-dev-to-render.sh" "$@"
