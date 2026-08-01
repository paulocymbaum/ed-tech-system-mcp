#!/usr/bin/env bash
# Aggregate CI job results into status-logs/, prune, and rebuild the status page manifest.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

SAFETY_RESULT="${SAFETY_RESULT:-success}"
VERIFY_RESULT="${VERIFY_RESULT:-success}"
MCP_IMAGE_RESULT="${MCP_IMAGE_RESULT:-success}"
DEPLOY_RESULT="${DEPLOY_RESULT:-skipped}"
DEPLOY_URL="${DEPLOY_URL:-}"
COVERAGE_FILE="${COVERAGE_FILE:-coverage.json}"
PYTEST_PASSED="${PYTEST_PASSED:-0}"
PYTEST_FAILED="${PYTEST_FAILED:-0}"
PYTEST_SKIPPED="${PYTEST_SKIPPED:-0}"

record_incident() {
  local incident_type="$1"
  local summary="$2"
  uv run python scripts/status/record_incident.py incident "$incident_type" --summary "$summary"
}

if [[ "$SAFETY_RESULT" == "failure" ]]; then
  record_incident securityGateFailure "Safety checks failed (gitleaks, hooks, or hook contract tests)."
fi

if [[ "$VERIFY_RESULT" == "failure" ]]; then
  record_incident qualityGateFailure "Pytest or architecture lint failed."
elif [[ "$VERIFY_RESULT" == "success" ]]; then
  args=(scripts/status/record_incident.py snapshot --coverage-file "$COVERAGE_FILE")
  args+=(--passed "$PYTEST_PASSED" --failed "$PYTEST_FAILED" --skipped "$PYTEST_SKIPPED")
  uv run python "${args[@]}"
fi

if [[ "$MCP_IMAGE_RESULT" == "failure" ]]; then
  record_incident qualityGateFailure "Docker MCP image build failed."
fi

if [[ "$DEPLOY_RESULT" == "failure" ]]; then
  record_incident deployFailure "Vercel production deploy failed."
elif [[ "$DEPLOY_RESULT" == "success" && -n "$DEPLOY_URL" ]]; then
  if ! curl -fsS --max-time 20 "${DEPLOY_URL%/}/health" >/dev/null; then
    record_incident availabilityLoss "Production /health probe failed after deploy."
  fi
fi

uv run python scripts/status/prune_logs.py
uv run python scripts/status/build_manifest.py
