#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

echo "Running pre-commit safety checks..."

bash scripts/hooks/verify-gitignore.sh
bash scripts/hooks/block-env-files.sh
bash scripts/hooks/scan-secrets.sh

echo "All pre-commit safety checks passed."
