#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)
DASH="$ROOT_DIR/.mcp/dashboard"
STATUS="$DASH/status.json"
SUMMARY="$DASH/coverage_summary.json"

echo "[jb-ui-verify] verifying status & coverage summary (if any) ..."

python3 - << 'PY'
import json, sys, os
from pathlib import Path
root = Path(os.getcwd())
dash = root/'.mcp'/'dashboard'
status = dash/'status.json'
if not status.exists():
    print('[jb-ui-verify] WARN: status.json missing; run dev-agent or status-update first')
    sys.exit(0)
S = json.loads(status.read_text(encoding='utf-8'))
plan = (S.get('plan') or {})
cov  = (S.get('coverage') or {})
print('[jb-ui-verify] plan.status =', plan.get('status'), 'current =', plan.get('current'))
print('[jb-ui-verify] coverage.count =', cov.get('count'), 'weak =', len(cov.get('weak') or []))
# Optional: coverage_summary.json
summary = dash/'coverage_summary.json'
if summary.exists():
    D = json.loads(summary.read_text(encoding='utf-8'))
    print('[jb-ui-verify] summary: weak=', len(D.get('weak') or []), 'near=', len(D.get('near') or []))
else:
    print('[jb-ui-verify] summary: not found (ok)')
PY

echo "[jb-ui-verify] done"
