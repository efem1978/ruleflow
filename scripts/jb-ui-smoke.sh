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

# Produce a lightweight snapshot markdown as“替代截图”材料
SS_DIR="$JB_DIR/screenshots"
mkdir -p "$SS_DIR"
SNAP="$SS_DIR/jb_ui_snapshot.md"

# Ensure status.json exists (best-effort)
python3 - << 'PY' >> "$LOG" 2>&1 || true
from pathlib import Path
import json, subprocess, sys, os
root = Path('..').resolve()
dash = root/'.mcp'/'dashboard'
dash.mkdir(parents=True, exist_ok=True)
status = dash/'status.json'
try:
    if not status.exists():
        subprocess.run([sys.executable, '-m', 'mcp_rules_assistant.cli', 'status-update'], check=False)
except Exception as e:
    print('[jb-ui-smoke] WARN: status-update failed:', e)
print('[jb-ui-smoke] status.json present =', status.exists())
PY

{
  echo "# JetBrains UI Smoke Snapshot"
  echo
  if [ -f "$ROOT_DIR/.mcp/dashboard/status.json" ]; then
    PYTHONIOENCODING=utf-8 python3 - << 'PY'
from pathlib import Path
import json
dash = Path('.mcp/dashboard')
S = json.loads((dash/'status.json').read_text(encoding='utf-8')) if (dash/'status.json').exists() else {}
plan = S.get('plan') or {}
cov  = S.get('coverage') or {}
print('**Plan**: status=', plan.get('status',''), '; current=', plan.get('current',''))
print('**Coverage**: files=', cov.get('count',0), '; weak=', len(cov.get('weak') or []))
PY
  else
    echo "(status.json not found)"
  fi
} > "$SNAP" 2>> "$LOG" || true

# Also generate storyboard artifacts (headless) as an alternative to screenshots
bash "$ROOT_DIR/scripts/jb-storyboard.sh" >> "$LOG" 2>&1 || true

echo "[jb-ui-smoke] done (log: $LOG, snapshot: $SNAP)" | tee -a "$LOG"
exit 0
