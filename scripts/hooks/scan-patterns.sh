#!/usr/bin/env bash
# Shared secret-detection patterns for hook scanners.

MAX_SCAN_FILE_SIZE=51200

is_env_named_path() {
  local base
  base="$(basename "$1" | tr '[:upper:]' '[:lower:]')"
  case "$base" in
    .env | .env.* | *.env | *.env.*)
      return 0
      ;;
  esac
  return 1
}

SECRET_CONTENT_PATTERNS=(
  '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
  'gsk_[a-zA-Z0-9]{20,}'
  'AKIA[0-9A-Z]{16}'
  'AIza[0-9A-Za-z\-_]{35}'
  'sk-[a-zA-Z0-9]{20,}'
  'xox[baprs]-[a-zA-Z0-9-]{10,}'
  'ghp_[a-zA-Z0-9]{36}'
  'github_pat_[a-zA-Z0-9_]{20,}'
  'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'
  'sb_secret_[a-zA-Z0-9]{20,}'
  'sbp_[a-zA-Z0-9]{20,}'
  'dp\.[a-zA-Z0-9._-]{20,}'
  'service_role[[:space:]]*[=:][[:space:]]*['\''"]?[a-zA-Z0-9_/=+-]{20,}'
  'VITE_[A-Z0-9_]*(SECRET|SERVICE_ROLE|PRIVATE_KEY|TOKEN)[A-Z0-9_]*[[:space:]]*[=:][[:space:]]*['\''"]?[a-zA-Z0-9_/=+-]{16,}'
)

SECRET_TOKEN_PREFIX_PATTERN='AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36,}|github_pat_[a-zA-Z0-9_]{22,}|sk-[a-zA-Z0-9]{20,}|xox[baprs]-[0-9a-zA-Z-]{10,}|gsk_[a-zA-Z0-9]{20,}|sb_secret_[a-zA-Z0-9]{20,}|sbp_[a-zA-Z0-9]{20,}|dp\.[a-zA-Z0-9._-]{20,}'

SECRET_ASSIGNMENT_PATTERN='(api[_-]?key|secret|password|token|auth)[[:space:]]*[=:][[:space:]]*['\''"]?[a-zA-Z0-9_\-+/=]{24,}'
