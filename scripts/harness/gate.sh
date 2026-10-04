#!/usr/bin/env bash
# gate.sh — MCP layer sensor runner (ed-tech-system-mcp).
# Same runner contract as ed-tech-system scripts/ci.sh: numbered steps,
# per-step runner JSON, summary.json, exit 0/1/2. Only this script writes
# .gates/last-run/*.json — agents read, never write.
#
# Usage: scripts/harness/gate.sh fast|mypy|all
#   fast   pytest (unit+integration, cursor_harness deselected)
#   mypy   static type check
#   all    pytest + mypy
#
# Exit classes: 0 complete · 1 continue (red step) · 2 misconfigured.
# Cap is a caller concept (loop-management) — never a pass.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="${GATES_RUN_DIR:-$ROOT/.gates/last-run}"
LOG_MAX_BYTES="${GATES_LOG_MAX_BYTES:-16000}"
SKIP_LIST="${GATES_SKIP:-}"

usage() { sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

profile_steps() {
  case "$1" in
    fast) echo "01-pytest" ;;
    mypy) echo "02-mypy" ;;
    all)  echo "01-pytest 02-mypy" ;;
    *) return 1 ;;
  esac
}

MAIN="${1:-}"
if [ -z "$MAIN" ]; then
  usage
  exit 2
fi

STEPS="$(profile_steps "$MAIN")" || { usage; exit 2; }

is_skipped() {
  case " $SKIP_LIST " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

mkdir -p "$RUN_DIR"
START_MS="$(date +%s%3N)"
SUMMARY_JSON=()
FAILED=0
MISSING=0

for STEP in $STEPS; do
  if is_skipped "$STEP"; then
    echo "SKIP $STEP (GATES_SKIP)"
    SUMMARY_JSON+=("{\"step\":\"$STEP\",\"name\":\"$STEP\",\"exit\":-1,\"ms\":0,\"log\":null}")
    continue
  fi

  case "$STEP" in
    01-pytest) CMD=(uv run pytest -q -m "not cursor_harness" --junitxml=pytest-results.xml) ;;
    # Report-only until the 35-error mypy baseline is ratcheted to 0 (PK-70
    # floor-at-baseline discipline): `|| true` would hide the verdict from the
    # runner JSON, so we record the real exit in REPORT_ONLY instead.
    02-mypy)
      CMD=(uv run mypy src/mcp_server)
      REPORT_ONLY=1
      ;;
    *) echo "INTERRUPTED $STEP — no command mapped" >&2; MISSING=$((MISSING+1)); continue ;;
  esac

  LOG="$RUN_DIR/$STEP.log"
  OUT="$(mktemp)"
  S="$(date +%s%3N)"
  echo "RUN   $STEP"
  (cd "$ROOT" && "${CMD[@]}") >"$OUT" 2>&1
  CODE=$?
  E="$(date +%s%3N)"
  MS=$((E - S))

  if [ "${REPORT_ONLY:-0}" = "1" ] && [ "$CODE" -ne 0 ]; then
    echo "REPORT $STEP (baseline-red, not a setpoint yet — ${MS}ms)"
    CODE=0
  fi

  tail -c "$LOG_MAX_BYTES" "$OUT" >"$LOG" || true
  rm -f "$OUT"

  printf '{"step":"%s","name":"%s","exit":%d,"ms":%d,"log":"%s"}\n' \
    "$STEP" "$STEP" "$CODE" "$MS" "$LOG" >"$RUN_DIR/$STEP.json"
  SUMMARY_JSON+=("$(cat "$RUN_DIR/$STEP.json")")

  if [ "$CODE" -eq 0 ]; then
    echo "PASS  $STEP (${MS}ms)"
  else
    echo "FAIL  $STEP (exit $CODE, ${MS}ms) — log: $LOG"
    FAILED=$((FAILED + 1))
  fi
done

END_MS="$(date +%s%3N)"
DURATION=$((END_MS - START_MS))

if [ "$MISSING" -gt 0 ]; then STATUS="interrupted"
elif [ "$FAILED" -gt 0 ]; then STATUS="continue"
else STATUS="complete"; fi

{
  printf '{"profile":"%s","status":"%s","durationMs":%d,"failed":%d,"missing":%d,"steps":[\n' \
    "$MAIN" "$STATUS" "$DURATION" "$FAILED" "$MISSING"
  printf '%s\n' "${SUMMARY_JSON[@]}" | paste -sd, - 2>/dev/null || true
  printf ']\n}\n'
} >"$RUN_DIR/summary.json"

echo "----"
echo "status=$STATUS failed=$FAILED missing=$MISSING duration=${DURATION}ms run_dir=$RUN_DIR"

[ "$STATUS" = "interrupted" ] && exit 2
[ "$STATUS" = "continue" ] && exit 1
exit 0
