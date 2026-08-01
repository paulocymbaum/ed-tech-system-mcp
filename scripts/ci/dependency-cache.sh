#!/usr/bin/env bash
# Hash-based dependency cache helpers for GitHub Actions CI.
# Usage: dependency-cache.sh <command> <group>
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="${DEPENDENCY_CACHE_ROOT:-$SCRIPT_ROOT}"

VERCEL_CLI_VERSION="58.4.4"

VALID_GROUPS=(
  python-hooks
  python-dev
  npm-root
  vercel-cli
  docker-mcp
)

usage() {
  cat <<'EOF' >&2
Usage: dependency-cache.sh <command> <group>

Commands:
  cache-key    Output deterministic cache key: {group}-{short-hash}
  cache-paths  Output newline-separated paths for actions/cache
  restore      Exit 0 if cached artifacts are valid, 1 otherwise
  install      Install dependencies (skip when restore succeeds)
  save         No-op (actions/cache handles persistence)

Groups:
  python-hooks  uv sync --frozen --extra full
  python-dev    uv sync --frozen --all-groups --extra full
  npm-root      npm ci
  vercel-cli    npm install --global vercel@58.4.4
  docker-mcp    Docker build inputs (cache key only; build in workflow)
EOF
  exit 1
}

die() {
  echo "dependency-cache.sh: $*" >&2
  exit 1
}

validate_group() {
  local group="$1"
  local valid
  for valid in "${VALID_GROUPS[@]}"; do
    if [[ "$group" == "$valid" ]]; then
      return 0
    fi
  done
  die "unknown group: $group"
}

hash_content() {
  sha256sum | awk '{print substr($1, 1, 12)}'
}

cache_key_material() {
  local group="$1"
  case "$group" in
    python-hooks)
      {
        printf '%s\n' "python-hooks"
        cat "$REPO_ROOT/pyproject.toml" "$REPO_ROOT/uv.lock"
        printf '%s\n' "--extra full"
      }
      ;;
    python-dev)
      {
        printf '%s\n' "python-dev"
        cat "$REPO_ROOT/pyproject.toml" "$REPO_ROOT/uv.lock"
        printf '%s\n' "--all-groups --extra full"
      }
      ;;
    npm-root)
      {
        printf '%s\n' "npm-root"
        cat "$REPO_ROOT/package-lock.json"
      }
      ;;
    vercel-cli)
      printf '%s\n' "vercel-cli" "$VERCEL_CLI_VERSION"
      ;;
    docker-mcp)
      {
        printf '%s\n' "docker-mcp"
        cat "$REPO_ROOT/Dockerfile" "$REPO_ROOT/pyproject.toml" "$REPO_ROOT/uv.lock"
      }
      ;;
    *)
      die "unknown group: $group"
      ;;
  esac
}

cmd_cache_key() {
  local group="$1"
  validate_group "$group"
  local short_hash
  short_hash="$(cache_key_material "$group" | hash_content)"
  printf '%s-%s\n' "$group" "$short_hash"
}

vercel_cli_cache_paths() {
  printf '%s\n' "${NPM_CONFIG_CACHE:-$HOME/.npm}"
  if command -v npm >/dev/null 2>&1; then
    local npm_prefix npm_root
    npm_prefix="$(npm prefix -g 2>/dev/null || true)"
    npm_root="$(npm root -g 2>/dev/null || true)"
    [[ -n "$npm_root" ]] && printf '%s\n' "$npm_root"
    if [[ -n "$npm_prefix" ]]; then
      printf '%s\n' "$npm_prefix/bin"
    fi
  fi
}

cmd_cache_paths() {
  local group="$1"
  validate_group "$group"
  case "$group" in
    python-hooks | python-dev)
      printf '%s\n' "$REPO_ROOT/.venv"
      printf '%s\n' "${UV_CACHE_DIR:-$HOME/.cache/uv}"
      ;;
    npm-root)
      printf '%s\n' "$REPO_ROOT/node_modules"
      ;;
    vercel-cli)
      vercel_cli_cache_paths
      ;;
    docker-mcp)
      # Docker BuildKit GHA cache is configured in the workflow.
      ;;
  esac
}

python_venv_valid() {
  [[ -x "$REPO_ROOT/.venv/bin/python" ]] && [[ -f "$REPO_ROOT/.venv/pyvenv.cfg" ]]
}

cmd_restore() {
  local group="$1"
  validate_group "$group"
  case "$group" in
    python-hooks | python-dev)
      python_venv_valid
      ;;
    npm-root)
      [[ -d "$REPO_ROOT/node_modules" ]] && [[ -f "$REPO_ROOT/node_modules/.package-lock.json" ]]
      ;;
    vercel-cli)
      command -v vercel >/dev/null 2>&1 \
        && vercel --version 2>/dev/null | grep -q "$VERCEL_CLI_VERSION"
      ;;
    docker-mcp)
      return 1
      ;;
  esac
}

cmd_install() {
  local group="$1"
  validate_group "$group"

  if cmd_restore "$group"; then
    echo "dependency-cache: $group cache valid, skipping install"
    return 0
  fi

  cd "$REPO_ROOT"
  case "$group" in
    python-hooks)
      uv sync --frozen --extra full
      ;;
    python-dev)
      uv sync --frozen --all-groups --extra full
      ;;
    npm-root)
      npm ci
      ;;
    vercel-cli)
      npm install --global "vercel@${VERCEL_CLI_VERSION}"
      ;;
    docker-mcp)
      die "docker-mcp install is handled by the CI workflow docker build step"
      ;;
  esac
}

cmd_save() {
  local group="$1"
  validate_group "$group"
  # actions/cache persists paths after install; nothing to do here.
  :
}

main() {
  if (($# != 2)); then
    usage
  fi

  local command="$1"
  local group="$2"

  case "$command" in
    cache-key) cmd_cache_key "$group" ;;
    cache-paths) cmd_cache_paths "$group" ;;
    restore) cmd_restore "$group" ;;
    install) cmd_install "$group" ;;
    save) cmd_save "$group" ;;
    *) usage ;;
  esac
}

main "$@"
