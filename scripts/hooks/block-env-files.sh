#!/usr/bin/env bash
set -euo pipefail

# Block any secret env file from being committed (allow .env.example only).
blocked=()

while IFS= read -r -d '' file; do
  base="$(basename "$file")"

  if [[ "$base" == ".env.example" ]]; then
    continue
  fi

  if [[ "$base" == .env* ]] || [[ "$base" == *.pem ]] || [[ "$base" == *.key ]]; then
    blocked+=("$file")
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

if ((${#blocked[@]} > 0)); then
  echo "ERROR: Refusing to commit secret environment files:" >&2
  printf '  - %s\n' "${blocked[@]}" >&2
  echo >&2
  echo "Only .env.example may be committed. Store real values in a gitignored .env or your secrets manager." >&2
  exit 1
fi

echo "✓ No secret env files staged"
