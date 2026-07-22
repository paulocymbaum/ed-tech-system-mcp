#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

required_patterns=(
  ".env"
  ".env.*"
  "*.env"
  "*.env.*"
  "scripts/doppler/*.env"
  ".venv/"
)

if [[ ! -f .gitignore ]]; then
  echo "ERROR: .gitignore is missing." >&2
  exit 1
fi

missing=()
for pattern in "${required_patterns[@]}"; do
  if ! grep -qxF "$pattern" .gitignore; then
    missing+=("$pattern")
  fi
done

if ((${#missing[@]} > 0)); then
  echo "ERROR: .gitignore is missing required patterns:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

check_ignored_probe() {
  local probe="$1"
  touch "$probe"
  trap 'rm -f "$probe"' RETURN

  if git check-ignore -q "$probe"; then
    echo "✓ $probe pattern is active in .gitignore"
    return 0
  fi

  echo "ERROR: $probe is not ignored by .gitignore." >&2
  return 1
}

check_ignored_probe ".env"
check_ignored_probe "secrets.dev.env"
check_ignored_probe "scripts/doppler/secrets.dev.env"

echo "✓ All env file patterns are ignored"
