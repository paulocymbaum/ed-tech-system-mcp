#!/usr/bin/env bash
# Shared sensitive-file predicates for Husky public-repo safety hooks.

is_sensitive_basename() {
  local base="$1"

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
  local base
  base="$(basename "$file")"

  if is_sensitive_basename "$base"; then
    return 0
  fi

  if [[ "$file" == scripts/doppler/* ]] && [[ "$base" == *.env ]]; then
    return 0
  fi

  # Agent changelog memory is gitignored; block force-adds.
  if [[ "$file" == changelog/* ]] || [[ "$file" == changelog ]]; then
    return 0
  fi

  return 1
}
