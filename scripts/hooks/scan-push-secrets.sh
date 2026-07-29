#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
hooks_dir="$(dirname -- "$0")"

zero_sha="0000000000000000000000000000000000000000"

push_refs=()
while read -r local_ref local_sha remote_ref remote_sha; do
  push_refs+=("$local_ref|$local_sha|$remote_ref|$remote_sha")
done

if ((${#push_refs[@]} == 0)); then
  exit 0
fi

get_push_commits() {
  local local_sha="$1"
  local remote_sha="$2"

  if [[ "$local_sha" == "$zero_sha" ]]; then
    return 0
  fi

  if [[ "$remote_sha" == "$zero_sha" ]]; then
    git rev-list "$local_sha" --not --remotes 2>/dev/null || git rev-list "$local_sha"
  else
    git rev-list "$remote_sha".."$local_sha" 2>/dev/null
  fi
}

get_gitleaks_log_range() {
  local local_sha="$1"
  local remote_sha="$2"

  if [[ "$remote_sha" == "$zero_sha" ]]; then
    printf '%s --not --remotes' "$local_sha"
  else
    printf '%s..%s' "$remote_sha" "$local_sha"
  fi
}

declare -A unique_commits=()
for ref_line in "${push_refs[@]}"; do
  IFS='|' read -r local_ref local_sha remote_ref remote_sha <<<"$ref_line"

  if [[ "$local_sha" == "$zero_sha" ]]; then
    continue
  fi

  while read -r commit; do
    unique_commits["$commit"]=1
  done < <(get_push_commits "$local_sha" "$remote_sha")
done

push_commits=()
for commit in "${!unique_commits[@]}"; do
  push_commits+=("$commit")
done

if ((${#push_commits[@]} == 0)); then
  exit 0
fi

scan_with_gitleaks() {
  local failed=0

  for ref_line in "${push_refs[@]}"; do
    IFS='|' read -r local_ref local_sha remote_ref remote_sha <<<"$ref_line"

    if [[ "$local_sha" == "$zero_sha" ]]; then
      continue
    fi

    local range
    range="$(get_gitleaks_log_range "$local_sha" "$remote_sha")"

    if gitleaks detect --source . --log-opts "$range" --redact --config .gitleaks.toml >/dev/null 2>&1; then
      continue
    fi

    echo "ERROR: gitleaks found secrets in commits being pushed." >&2
    gitleaks detect --source . --log-opts "$range" --redact --config .gitleaks.toml >&2 || true
    failed=1
  done

  return "$failed"
}

scan_with_secretlint() {
  local commit file

  for commit in "${push_commits[@]}"; do
    while IFS= read -r -d '' file; do
      if is_scan_allowlisted_path "$file"; then
        continue
      fi

      if ! git show "$commit:$file" 2>/dev/null | node_modules/.bin/secretlint \
        --secretlintrc .secretlintrc.json \
        --stdinFileName="$file" >/dev/null 2>&1; then
        echo "ERROR: secretlint found secrets in commits being pushed." >&2
        git show "$commit:$file" 2>/dev/null | node_modules/.bin/secretlint \
          --secretlintrc .secretlintrc.json \
          --stdinFileName="$file" >&2 || true
        return 1
      fi
    done < <(git diff-tree --no-commit-id --name-only -r -z "$commit")
  done

  return 0
}

# shellcheck source=scan-allowlist.sh
source "$hooks_dir/scan-allowlist.sh"

scanners_available=0
scanners_failed=0

if command -v gitleaks >/dev/null 2>&1; then
  scanners_available=$((scanners_available + 1))
  if ! scan_with_gitleaks; then
    scanners_failed=1
  fi
fi

if [[ -x node_modules/.bin/secretlint ]]; then
  scanners_available=$((scanners_available + 1))
  if ! scan_with_secretlint; then
    scanners_failed=1
  fi
fi

if ((scanners_failed != 0)); then
  exit 1
fi

if ((scanners_available > 0)); then
  exit 0
fi

# shellcheck source=scan-file-content.sh
source "$hooks_dir/scan-file-content.sh"
scan_git_blobs_for_secrets "commits being pushed" "${push_commits[@]}"
