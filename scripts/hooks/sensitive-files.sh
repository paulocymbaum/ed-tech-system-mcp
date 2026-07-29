#!/usr/bin/env bash
# Shared sensitive-file predicates for Husky public-repo safety hooks.

is_sensitive_basename() {
  local base
  base="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"

  case "$base" in
    .env* | *.env | *.env.*)
      return 0
      ;;
    *.pem | *.key | *.p12 | *.pfx | *.p8 | *.jks | *.keystore)
      return 0
      ;;
    id_rsa | id_rsa.pub | id_ed25519 | id_ed25519.pub | id_ecdsa | id_ecdsa.pub)
      return 0
      ;;
    .npmrc | .pypirc)
      return 0
      ;;
    credentials.json | secrets.json | service-account*.json | mcp.json)
      return 0
      ;;
  esac

  return 1
}

is_sensitive_path() {
  local file="$1"
  local base base_lower
  base="$(basename "$file")"
  base_lower="$(printf '%s' "$base" | tr '[:upper:]' '[:lower:]')"

  if is_sensitive_basename "$base"; then
    return 0
  fi

  if [[ "$file" == scripts/doppler/* ]] && [[ "$base_lower" == *.env ]]; then
    return 0
  fi

  # Agent changelog memory is gitignored; block force-adds.
  if [[ "$file" == changelog/* ]] || [[ "$file" == changelog ]]; then
    return 0
  fi

  # Cursor IDE config is gitignored; block force-adds.
  if [[ "$file" == .cursor/* ]] || [[ "$file" == .cursor ]] || [[ "$base_lower" == "cursor.md" ]]; then
    return 0
  fi

  return 1
}
