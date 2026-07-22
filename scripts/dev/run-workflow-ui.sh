#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

export APP_ENV="${APP_ENV:-development}"
export LOCAL_UI_HOST="${LOCAL_UI_HOST:-127.0.0.1}"
export LOCAL_UI_PORT="${LOCAL_UI_PORT:-8877}"

if [[ ! -d "ui/node_modules" ]]; then
  echo "Installing UI dependencies..."
  npm --prefix ui install
fi

echo "Starting FastAPI workflow API on http://${LOCAL_UI_HOST}:${LOCAL_UI_PORT}"
uv run workflow-ui &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 1

echo "Starting React dev server on http://127.0.0.1:4173"
npm --prefix ui run dev
