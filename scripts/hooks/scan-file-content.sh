#!/usr/bin/env bash
# Shared regex fallback for secret patterns in arbitrary file lists.

# shellcheck source=scan-allowlist.sh
source "$(dirname -- "$0")/scan-allowlist.sh"
# shellcheck source=scan-patterns.sh
source "$(dirname -- "$0")/scan-patterns.sh"

_content_matches_secret_patterns() {
  local content="$1"
  local pattern

  for pattern in "${SECRET_CONTENT_PATTERNS[@]}"; do
    if grep -qE -e "$pattern" <<<"$content"; then
      return 0
    fi
  done

  return 1
}

_content_is_probably_binary() {
  local content="$1"
  local nul_count
  nul_count="$(printf '%s' "$content" | LC_ALL=C tr -cd '\0' | wc -c | tr -d ' ')"
  ((nul_count > 0))
}

scan_files_for_secrets() {
  local label="${1:-files}"
  shift

  if (("$#" == 0)); then
    return 0
  fi

  local findings=()
  local file pattern size

  for file in "$@"; do
    if [[ ! -f "$file" ]]; then
      continue
    fi

    if is_scan_allowlisted_path "$file"; then
      continue
    fi

    size=$(wc -c <"$file" | tr -d ' ')
    if ((size > MAX_SCAN_FILE_SIZE)); then
      continue
    fi

    for pattern in "${SECRET_CONTENT_PATTERNS[@]}"; do
      if grep -qE -e "$pattern" "$file" 2>/dev/null; then
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

scan_git_blobs_for_secrets() {
  local label="${1:-commits being pushed}"
  shift

  if (("$#" == 0)); then
    return 0
  fi

  local findings=()
  local commit file size

  for commit in "$@"; do
    while IFS= read -r -d '' file; do
      if is_scan_allowlisted_path "$file"; then
        continue
      fi

      local blob_content
      if ! blob_content="$(git show "$commit:$file" 2>/dev/null)"; then
        continue
      fi

      if _content_is_probably_binary "$blob_content"; then
        continue
      fi

      size=${#blob_content}
      if ((size > MAX_SCAN_FILE_SIZE)); then
        continue
      fi

      if _content_matches_secret_patterns "$blob_content"; then
        findings+=("$file (commit ${commit:0:7})")
      fi
    done < <(git diff-tree --no-commit-id --name-only -r -z "$commit")
  done

  if ((${#findings[@]} > 0)); then
    echo "ERROR: potential secrets in ${label}:" >&2
    printf '  - %s\n' "${findings[@]}" >&2
    return 1
  fi

  return 0
}
