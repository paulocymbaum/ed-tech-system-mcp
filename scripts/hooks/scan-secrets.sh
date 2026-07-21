#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

staged_files=()
while IFS= read -r -d '' file; do
  staged_files+=("$file")
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

if ((${#staged_files[@]} == 0)); then
  echo "✓ No staged files to scan"
  exit 0
fi

scan_with_gitleaks() {
  if command -v gitleaks >/dev/null 2>&1; then
    echo "→ Scanning staged changes with gitleaks"
    gitleaks protect --staged --verbose --redact --config .gitleaks.toml
    echo "✓ gitleaks passed"
    return 0
  fi
  return 1
}

scan_with_secretlint() {
  if [[ -x node_modules/.bin/secretlint ]]; then
    echo "→ Scanning staged files with secretlint"
    local file
    for file in "${staged_files[@]}"; do
      if ! node_modules/.bin/secretlint --secretlintrc .secretlintrc.json "$file"; then
        echo "ERROR: secretlint detected potential secrets in staged files." >&2
        return 1
      fi
    done
    echo "✓ secretlint passed"
    return 0
  fi
  return 1
}

if scan_with_gitleaks; then
  exit 0
fi

if scan_with_secretlint; then
  exit 0
fi

echo "ERROR: Secret scan failed or no scanner is available." >&2
echo "Run 'npm install' in the repo root, or install gitleaks: https://github.com/gitleaks/gitleaks" >&2
exit 1
