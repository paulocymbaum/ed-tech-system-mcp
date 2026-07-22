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

if command -v fuser >/dev/null 2>&1; then
  fuser -k "${LOCAL_UI_PORT}/tcp" 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
  stale_pid="$(lsof -ti tcp:"${LOCAL_UI_PORT}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${stale_pid}" ]]; then
    kill "${stale_pid}" 2>/dev/null || true
  fi
fi

if command -v doppler >/dev/null 2>&1 && doppler configure get config >/dev/null 2>&1; then
  doppler run -- uv run workflow-ui &
else
  uv run workflow-ui &
fi
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

sleep 1

echo "Starting React dev server on http://127.0.0.1:4173"
npm --prefix ui run dev
