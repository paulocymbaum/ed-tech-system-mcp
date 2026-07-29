#!/usr/bin/env bash
# Paths exempt from staged content/entropy scans (docs and scanner config only).

is_scan_allowlisted_path() {
  local file="$1"
  case "$file" in
    ENVIRONMENT_SETUP.md | ARCHITECTURE.md | package-lock.json | .gitleaks.toml | .secretlintrc.json)
      return 0
      ;;
  esac
  return 1
}
