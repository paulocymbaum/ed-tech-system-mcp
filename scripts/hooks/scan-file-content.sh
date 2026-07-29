#!/usr/bin/env bash
# Shared regex fallback for secret patterns in arbitrary file lists.

# shellcheck source=scan-allowlist.sh
source "$(dirname -- "$0")/scan-allowlist.sh"

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
)

scan_files_for_secrets() {
  local label="${1:-files}"
  shift

  if (("$#" == 0)); then
    return 0
  fi

  local findings=()
  local file pattern

  for file in "$@"; do
    if [[ ! -f "$file" ]]; then
      continue
    fi

    if is_scan_allowlisted_path "$file"; then
      continue
    fi

    for pattern in "${SECRET_CONTENT_PATTERNS[@]}"; do
      if grep -qE "$pattern" "$file" 2>/dev/null; then
        findings+=("$file")
        break
      fi
    done
  done

  if ((${#findings[@]} > 0)); then
    echo "ERROR: potential secrets in ${label}:" >&2
    printf '  - %s\n' "${findings[@]}" >&2
    return 1
  fi

  return 0
}
