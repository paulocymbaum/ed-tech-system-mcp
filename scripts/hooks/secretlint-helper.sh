#!/usr/bin/env bash
# Shared secretlint invocation with tool-error vs finding discrimination.

SECRETLINT_BIN="${SECRETLINT_BIN:-node_modules/.bin/secretlint}"
SECRETLINTRC="${SECRETLINTRC:-.secretlintrc.json}"

_is_secretlint_tool_failure() {
  local stderr_file="$1"

  if [[ ! -s "$stderr_file" ]]; then
    return 1
  fi

  if grep -qE '(^Error:| is not in cwd|ENOENT|Cannot find module|EACCES|secretlint failed)' "$stderr_file"; then
    return 0
  fi

  return 1
}

run_secretlint_on_files() {
  local label="$1"
  shift

  if (("$#" == 0)); then
    return 0
  fi

  local stderr_file
  stderr_file="$(mktemp)"
  if "$SECRETLINT_BIN" --secretlintrc "$SECRETLINTRC" "$@" >/dev/null 2>"$stderr_file"; then
    rm -f "$stderr_file"
    return 0
  fi

  if _is_secretlint_tool_failure "$stderr_file"; then
    echo "ERROR: secretlint scanner failed on ${label}:" >&2
    cat "$stderr_file" >&2
    rm -f "$stderr_file"
    return 2
  fi

  echo "ERROR: secretlint found secrets in ${label}." >&2
  "$SECRETLINT_BIN" --secretlintrc "$SECRETLINTRC" "$@" >&2 || true
  rm -f "$stderr_file"
  return 1
}

run_secretlint_on_stdin() {
  local label="$1"
  local filename="$2"
  local stderr_file
  stderr_file="$(mktemp)"

  if "$SECRETLINT_BIN" --secretlintrc "$SECRETLINTRC" --stdinFileName="$filename" >/dev/null 2>"$stderr_file"; then
    rm -f "$stderr_file"
    return 0
  fi

  if _is_secretlint_tool_failure "$stderr_file"; then
    echo "ERROR: secretlint scanner failed on ${label} (${filename}):" >&2
    cat "$stderr_file" >&2
    rm -f "$stderr_file"
    return 2
  fi

  echo "ERROR: secretlint found secrets in ${label} (${filename})." >&2
  "$SECRETLINT_BIN" --secretlintrc "$SECRETLINTRC" --stdinFileName="$filename" >&2 || true
  rm -f "$stderr_file"
  return 1
}
