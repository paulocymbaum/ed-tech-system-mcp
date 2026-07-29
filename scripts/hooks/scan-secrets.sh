#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
hooks_dir="$(dirname -- "$0")"

staged_files=()
while IFS= read -r -d '' file; do
  if [[ -f "$file" ]]; then
    staged_files+=("$file")
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

if ((${#staged_files[@]} == 0)); then
  exit 0
fi

scan_with_gitleaks() {
  if gitleaks protect --staged --redact --config .gitleaks.toml >/dev/null 2>&1; then
    return 0
  fi
  echo "ERROR: gitleaks found secrets in staged files." >&2
  gitleaks protect --staged --redact --config .gitleaks.toml >&2 || true
  return 1
}

scan_with_secretlint() {
  if node_modules/.bin/secretlint --secretlintrc .secretlintrc.json "${staged_files[@]}" >/dev/null 2>&1; then
    return 0
  fi
  echo "ERROR: secretlint found secrets in staged files." >&2
  node_modules/.bin/secretlint --secretlintrc .secretlintrc.json "${staged_files[@]}" >&2 || true
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

bash "$hooks_dir/scan-staged-content.sh"
