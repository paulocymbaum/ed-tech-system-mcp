#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# shellcheck source=scan-file-content.sh
source "$(dirname -- "$0")/scan-file-content.sh"

staged_files=()
while IFS= read -r -d '' file; do
  if [[ -f "$file" ]]; then
    staged_files+=("$file")
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

if ((${#staged_files[@]} == 0)); then
  exit 0
fi

scan_files_for_secrets "staged files" "${staged_files[@]}"
