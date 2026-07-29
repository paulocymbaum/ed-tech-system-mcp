#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# shellcheck source=lib/scan-allowlist.sh
source "$(dirname -- "$0")/lib/scan-allowlist.sh"

MAX_FILE_SIZE=51200

staged_files=()
while IFS= read -r -d '' file; do
  if [[ -f "$file" ]]; then
    staged_files+=("$file")
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

if ((${#staged_files[@]} == 0)); then
  exit 0
fi

is_probably_binary() {
  local file="$1"
  if command -v file >/dev/null 2>&1; then
    local mime
    mime="$(file -b --mime-type "$file" 2>/dev/null || true)"
    case "$mime" in
      image/* | audio/* | video/* | application/octet-stream | application/pdf | application/gzip | application/zip | application/x-*)
        return 0
        ;;
    esac
  fi
  return 1
}

findings=()

for file in "${staged_files[@]}"; do
  if is_scan_allowlisted_path "$file"; then
    continue
  fi

  if is_probably_binary "$file"; then
    continue
  fi

  size=$(wc -c <"$file" | tr -d ' ')
  if ((size > MAX_FILE_SIZE)); then
    continue
  fi

  if grep -qE 'AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36,}|github_pat_[a-zA-Z0-9_]{22,}|sk-[a-zA-Z0-9]{20,}|xox[baprs]-[0-9a-zA-Z-]{10,}' "$file" 2>/dev/null; then
    findings+=("$file: token prefix")
    continue
  fi

  if grep -qiE '(api[_-]?key|secret|password|token|auth)[[:space:]]*[=:][[:space:]]*['\''"]?[a-zA-Z0-9_\-+/=]{24,}' "$file" 2>/dev/null; then
    findings+=("$file: suspicious assignment")
  fi
done

if ((${#findings[@]} > 0)); then
  echo "ERROR: potential secrets in staged files:" >&2
  printf '  - %s\n' "${findings[@]}" >&2
  exit 1
fi
