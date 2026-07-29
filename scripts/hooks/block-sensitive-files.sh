#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=sensitive-files.sh
source "$(dirname -- "$0")/sensitive-files.sh"

blocked=()

while IFS= read -r -d '' file; do
  if is_sensitive_path "$file"; then
    blocked+=("$file")
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

if ((${#blocked[@]} > 0)); then
  echo "ERROR: sensitive files staged:" >&2
  printf '  - %s\n' "${blocked[@]}" >&2
  exit 1
fi
