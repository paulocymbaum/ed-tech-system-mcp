#!/usr/bin/env bash
# Run recursive-loop / Cursor harness tests (local .cursor/skills scripts + changelog).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SCRIPT_DIR=".cursor/skills/recursive-loop/scripts"
if [[ ! -f "$SCRIPT_DIR/verify-condition.sh" ]]; then
  echo "ERROR: $SCRIPT_DIR/verify-condition.sh not found." >&2
  echo "Cursor harness tests need local .cursor/skills/recursive-loop scripts." >&2
  exit 1
fi

echo "→ Cursor harness tests (recursive-loop agent scripts)"
uv run pytest -m cursor_harness -q "$@"
