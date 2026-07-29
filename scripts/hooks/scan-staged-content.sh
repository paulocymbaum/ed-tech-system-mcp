#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# shellcheck source=lib/scan-allowlist.sh
source "$(dirname -- "$0")/lib/scan-allowlist.sh"

PATTERNS=(
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

staged_files=()
while IFS= read -r -d '' file; do
  if [[ -f "$file" ]]; then
    staged_files+=("$file")
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

if ((${#staged_files[@]} == 0)); then
  exit 0
fi

findings=()
for file in "${staged_files[@]}"; do
  if is_scan_allowlisted_path "$file"; then
    continue
  fi

  for pattern in "${PATTERNS[@]}"; do
    if grep -qE "$pattern" "$file" 2>/dev/null; then
      findings+=("$file")
      break
    fi
  done
done

if ((${#findings[@]} > 0)); then
  echo "ERROR: potential secrets in staged files:" >&2
  printf '  - %s\n' "${findings[@]}" >&2
  exit 1
fi
