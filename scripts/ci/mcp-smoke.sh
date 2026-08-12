#!/usr/bin/env bash
# Run MCP HTTP smoke checks against a running server (local Docker or Render).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BASE_URL="${MCP_BASE_URL:-http://127.0.0.1:8000}"
TIMEOUT="${MCP_SMOKE_TIMEOUT:-120}"
QUERY="${MCP_SMOKE_QUERY:-smoke test}"

exec uv run python scripts/ci/mcp_smoke.py \
  --base-url "$BASE_URL" \
  --timeout "$TIMEOUT" \
  --query "$QUERY"
