#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

required_patterns=(
  ".env"
  ".env.*"
  "!.env.example"
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

# Prove .env would be ignored if it existed.
if ! git check-ignore -q .env 2>/dev/null; then
  # git check-ignore returns 1 when the path is not ignored; create a temp probe.
  probe=".env.__husky_probe__"
  touch "$probe"
  trap 'rm -f "$probe"' EXIT

  if git check-ignore -q "$probe"; then
    echo "✓ .env pattern is active in .gitignore"
  else
    echo "ERROR: .env is not ignored by .gitignore." >&2
    exit 1
  fi
else
  echo "✓ .env is ignored by .gitignore"
fi

if git check-ignore -q .env.example; then
  echo "ERROR: .env.example must remain committable (not ignored)." >&2
  exit 1
fi

echo "✓ .env.example is not ignored"
