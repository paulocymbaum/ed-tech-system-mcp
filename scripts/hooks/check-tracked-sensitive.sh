#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# shellcheck source=sensitive-files.sh
source "$(dirname -- "$0")/sensitive-files.sh"

tracked=()
while IFS= read -r -d '' file; do
  if is_sensitive_path "$file"; then
    tracked+=("$file")
  fi
done < <(git ls-files -z)

if ((${#tracked[@]} > 0)); then
  echo "ERROR: sensitive files tracked in git:" >&2
  printf '  - %s\n' "${tracked[@]}" >&2
  exit 1
fi
