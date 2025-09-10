#!/usr/bin/env bash
set -euo pipefail

# JetBrains headless UI smoke (non-blocking): try to start IDE sandbox briefly.
# - Runs under xvfb-run if available; otherwise falls back to normal run.
# - Timeboxed to ~20s, then terminates, returning success.
# - Outputs minimal logs to extensions/jetbrains/ui_smoke.log

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
JB_DIR="$ROOT_DIR/extensions/jetbrains"
LOG="$JB_DIR/ui_smoke.log"

cd "$JB_DIR"


echo "[jb-ui-smoke] starting headless runIde (timeboxed) ..." | tee "$LOG"

CMD='./gradlew runIde -i || gradle runIde -i'
if command -v xvfb-run >/dev/null 2>&1; then
  ( timeout 20s xvfb-run -a bash -lc "$CMD" ) >> "$LOG" 2>&1 || true
else
  ( timeout 20s bash -lc "$CMD" ) >> "$LOG" 2>&1 || true
fi

echo "[jb-ui-smoke] done (log: $LOG)" | tee -a "$LOG"
exit 0
