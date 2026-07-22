#!/usr/bin/env bash
set -euo pipefail

# Block sensitive artifacts from being committed — secrets live in Doppler or a local gitignored .env.
blocked=()

is_sensitive_file() {
  local file="$1"
  local base
  base="$(basename "$file")"

  if [[ "$base" == .env* ]] \
    || [[ "$base" == *.env ]] \
    || [[ "$base" == *.env.* ]] \
    || [[ "$base" == *.pem ]] \
    || [[ "$base" == *.key ]] \
    || [[ "$base" == *.p12 ]] \
    || [[ "$base" == *.pfx ]] \
    || [[ "$base" == credentials.json ]] \
    || [[ "$base" == secrets.json ]] \
    || [[ "$base" == service-account*.json ]]; then
    return 0
  fi

  if [[ "$file" == scripts/doppler/* ]] && [[ "$base" == *.env ]]; then
    return 0
  fi

  return 1
}

while IFS= read -r -d '' file; do
  if is_sensitive_file "$file"; then
    blocked+=("$file")
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR)

if ((${#blocked[@]} > 0)); then
  echo "ERROR: Refusing to commit sensitive files:" >&2
  printf '  - %s\n' "${blocked[@]}" >&2
  echo >&2
  echo "Sensitive files must stay out of git. Use Doppler or a local gitignored .env file." >&2
  exit 1
fi

echo "✓ No sensitive files staged"
