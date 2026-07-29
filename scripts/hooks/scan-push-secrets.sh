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

declare -A unique_files=()
for ref_line in "${push_refs[@]}"; do
  IFS='|' read -r local_ref local_sha remote_ref remote_sha <<<"$ref_line"

  if [[ "$local_sha" == "$zero_sha" ]]; then
    continue
  fi

  if [[ "$remote_sha" == "$zero_sha" ]]; then
    while read -r commit; do
      while IFS= read -r -d '' file; do
        if [[ -f "$file" ]]; then
          unique_files["$file"]=1
        fi
      done < <(git diff-tree --no-commit-id --name-only -r -z "$commit")
    done < <(git rev-list "$local_sha")
  else
    while IFS= read -r -d '' file; do
      if [[ -f "$file" ]]; then
        unique_files["$file"]=1
      fi
    done < <(git diff --name-only -z "$remote_sha".."$local_sha")
  fi
done

push_files=()
for file in "${!unique_files[@]}"; do
  push_files+=("$file")
done

if ((${#push_files[@]} == 0)); then
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
    if [[ "$remote_sha" == "$zero_sha" ]]; then
      range="$local_sha"
    else
      range="$remote_sha..$local_sha"
    fi

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
  if node_modules/.bin/secretlint --secretlintrc .secretlintrc.json "${push_files[@]}" >/dev/null 2>&1; then
    return 0
  fi

  echo "ERROR: secretlint found secrets in commits being pushed." >&2
  node_modules/.bin/secretlint --secretlintrc .secretlintrc.json "${push_files[@]}" >&2 || true
  return 1
}

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
scan_files_for_secrets "commits being pushed" "${push_files[@]}"
