#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# shellcheck source=scan-allowlist.sh
source "$(dirname -- "$0")/scan-allowlist.sh"
# shellcheck source=scan-patterns.sh
source "$(dirname -- "$0")/scan-patterns.sh"

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

  if is_probably_binary "$file" && ! is_env_named_path "$file"; then
    echo "WARN: scan-entropy.sh skipped path=${file} rule=binary" >&2
    continue
  fi

  size=$(wc -c <"$file" | tr -d ' ')
  if ((size > MAX_SCAN_FILE_SIZE)) && ! is_env_named_path "$file"; then
    echo "WARN: scan-entropy.sh skipped path=${file} rule=size" >&2
    continue
  fi

  if grep -qE "$SECRET_TOKEN_PREFIX_PATTERN" "$file" 2>/dev/null; then
    findings+=("$file: token prefix")
    continue
  fi

  if grep -qiE "$SECRET_ASSIGNMENT_PATTERN" "$file" 2>/dev/null; then
    findings+=("$file: suspicious assignment")
  fi
done

if ((${#findings[@]} > 0)); then
  echo "ERROR: potential secrets in staged files:" >&2
  printf '  - %s\n' "${findings[@]}" >&2
  exit 1
fi
