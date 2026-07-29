#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

bash scripts/hooks/pre-push-safety.sh
bash scripts/lint/architecture.sh
