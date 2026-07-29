#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

required_patterns=(
  ".env"
  ".env.*"
  "*.env"
  "*.env.*"
  ".ENV"
  ".ENV.*"
  "*.ENV"
  "*.ENV.*"
  "scripts/doppler/*.env"
  ".venv/"
  "id_rsa"
  "id_ed25519"
  ".npmrc"
  ".NPMRC"
  ".pypirc"
  ".PYPIRC"
  "*.p8"
  "*.jks"
  "*.pem"
  "*.PEM"
  "*.key"
  "*.KEY"
  "changelog/"
  "mcp.json"
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
  echo "ERROR: .gitignore missing patterns:" >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

tracked_violations=()
while IFS= read -r -d '' file; do
  if git check-ignore --no-index -q "$file"; then
    tracked_violations+=("$file")
  fi
done < <(git ls-files -z)

if ((${#tracked_violations[@]} > 0)); then
  echo "ERROR: tracked files match .gitignore:" >&2
  printf '  - %s\n' "${tracked_violations[@]}" >&2
  exit 1
fi

check_ignored_probe() {
  local probe="$1"
  mkdir -p "$(dirname -- "$probe")"
  touch "$probe"
  trap 'rm -f "$probe"' RETURN

  if git check-ignore -q "$probe"; then
    return 0
  fi

  echo "ERROR: $probe not ignored by .gitignore." >&2
  return 1
}

check_ignored_probe ".env.husky-probe"
check_ignored_probe ".ENV.husky-probe"
check_ignored_probe ".NPMRC"
check_ignored_probe "secrets.dev.env"
check_ignored_probe "scripts/doppler/secrets.dev.env"
