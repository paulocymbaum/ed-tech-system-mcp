#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

bash scripts/hooks/verify-gitignore.sh
bash scripts/hooks/check-tracked-sensitive.sh
bash scripts/hooks/scan-push-secrets.sh
