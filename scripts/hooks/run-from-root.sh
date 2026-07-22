#!/usr/bin/env bash
set -euo pipefail

if (($# == 0)); then
  echo "Usage: run-from-root.sh <command> [args...]" >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"
exec "$@"
