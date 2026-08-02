#!/usr/bin/env bash
# Shared Doppler auth helpers for CI deploy scripts (dev + github_ci configs).
set -euo pipefail

DOPPLER_PROJECT="${DOPPLER_PROJECT:-ed-harness-system}"
DOPPLER_DEV_CONFIG="${DOPPLER_DEV_CONFIG:-dev}"
DOPPLER_GITHUB_CI_CONFIG="${DOPPLER_GITHUB_CI_CONFIG:-github_ci}"

doppler_dev_token() {
  printf '%s' "${DOPPLER_TOKEN:-}"
}

doppler_github_ci_token() {
  if [[ -n "${DOPPLER_GITHUB_CI_TOKEN:-}" ]]; then
    printf '%s' "$DOPPLER_GITHUB_CI_TOKEN"
    return 0
  fi
  doppler_dev_token
}

doppler_get_secret() {
  local config="$1"
  local key="$2"
  local token="$3"
  if [[ -n "$token" ]]; then
    doppler secrets get "$key" \
      --project "$DOPPLER_PROJECT" \
      --config "$config" \
      --plain \
      --token "$token"
    return
  fi
  doppler secrets get "$key" \
    --project "$DOPPLER_PROJECT" \
    --config "$config" \
    --plain
}

doppler_get_dev_secret() {
  doppler_get_secret "$DOPPLER_DEV_CONFIG" "$1" "$(doppler_dev_token)"
}

doppler_get_github_ci_secret() {
  doppler_get_secret "$DOPPLER_GITHUB_CI_CONFIG" "$1" "$(doppler_github_ci_token)"
}
