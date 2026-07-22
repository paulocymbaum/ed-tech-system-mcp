#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo_root"

lint_root="${ARCHITECTURE_LINT_ROOT:-src/mcp_server}"
violations=()

search_python_files() {
  local pattern="$1"
  local search_path="$2"

  if command -v rg >/dev/null 2>&1; then
    rg -n --glob '*.py' "$pattern" "$search_path" 2>/dev/null || true
    return
  fi

  if command -v grep >/dev/null 2>&1; then
    grep -RInE --include='*.py' "$pattern" "$search_path" 2>/dev/null || true
    return
  fi

  echo "ERROR: Architecture lint requires ripgrep (rg) or grep." >&2
  exit 1
}

collect_matches() {
  local label="$1"
  local pattern="$2"
  local search_path="$3"
  local match

  while IFS= read -r match; do
    [[ -n "$match" ]] && violations+=("[$label] $match")
  done < <(search_python_files "$pattern" "$search_path")
}

# Anti-patterns in application/ and interface/ (ARCHITECTURE.md)
for layer in application interface; do
  layer_dir="$lint_root/$layer"
  [[ -d "$layer_dir" ]] || continue
  collect_matches "infra-adapter-in-$layer" \
    'SupabaseRepository|YouTubeDataApiClient|DuckDuckGoSearchClient|from supabase|googleapiclient|create_client\(' \
    "$layer_dir"
done

# load_dotenv(override=True) is forbidden everywhere
collect_matches "load-dotenv-override" \
  'load_dotenv\([^)]*override=True' \
  "$lint_root"

# load_dotenv allowed only in main.py
while IFS= read -r match; do
  file="${match%%:*}"
  if [[ "$(basename "$file")" != "main.py" ]]; then
    violations+=("[load-dotenv-outside-main] $match")
  fi
done < <(search_python_files 'load_dotenv' "$lint_root")

# settings import allowed only in main.py and wiring.py
while IFS= read -r match; do
  file="${match%%:*}"
  base="$(basename "$file")"
  if [[ "$base" != "main.py" && "$base" != "wiring.py" ]]; then
    violations+=("[settings-import-outside-entrypoint] $match")
  fi
done < <(search_python_files 'from mcp_server\.settings import|import mcp_server\.settings' "$lint_root")

if ((${#violations[@]} > 0)); then
  echo "ERROR: Architecture boundary pattern violations:" >&2
  printf '  %s\n' "${violations[@]}" >&2
  exit 1
fi

echo "✓ Architecture boundary patterns passed"
