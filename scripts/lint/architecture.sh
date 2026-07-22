#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

echo "Running architecture linter..."

bash scripts/lint/lint-imports.sh
bash scripts/lint/check-boundary-patterns.sh

echo "All architecture lint checks passed."
