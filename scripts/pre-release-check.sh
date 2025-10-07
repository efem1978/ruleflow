#!/usr/bin/env bash
set -euo pipefail

# Pre-release checklist runner
# - Generates report at .mcp/dashboard/pre_release_report.md
# - Composes full release body at .mcp/dashboard/release_body.md
#
# Options via env:
#   LCOV_THRESHOLD (default 80)
#   WITH_DOCKER_VERIFY=1 to run docker compose verify

OUT_DIR=".mcp/dashboard"
REPORT="$OUT_DIR/pre_release_report.md"
LCOV_THRESHOLD="${LCOV_THRESHOLD:-80}"
WITH_DOCKER_VERIFY="${WITH_DOCKER_VERIFY:-0}"

mkdir -p "$OUT_DIR"

echo "[pre-release] Status refresh"
python3 -m mcp_rules_assistant.cli status-update --json > "$OUT_DIR/status.json" || true

echo "[pre-release] Release simulation (tests/coverage/vscode/license/package)"
bash scripts/release-simulate.sh >/dev/null 2>&1 || true

echo "[pre-release] Compose release body"
BODY_PATH=$(bash scripts/release-compose-body.sh)

DOCKER_OK="SKIPPED"
if [ "$WITH_DOCKER_VERIFY" = "1" ]; then
  if command -v docker >/dev/null 2>&1; then
    echo "[pre-release] docker verify"
    if docker compose run --rm verify; then
      DOCKER_OK="OK"
    else
      DOCKER_OK="FAIL"
    fi
  else
    DOCKER_OK="SKIPPED (docker not found)"
  fi
fi

# Evaluate VS Code lcov gate against threshold (best-effort)
LCOV_OK="SKIPPED"
if [ -f extensions/vscode/coverage/lcov.info ]; then
  if sh scripts/check-lcov.sh extensions/vscode/coverage/lcov.info "$LCOV_THRESHOLD" gate; then
    LCOV_OK="OK (>=${LCOV_THRESHOLD}%)"
  else
    LCOV_OK="FAIL (<${LCOV_THRESHOLD}%)"
  fi
fi

# Pull release simulation quick summary lines
REL_SIM="$OUT_DIR/release_check.md"
SIM_LINES=""
if [ -f "$REL_SIM" ]; then
  SIM_LINES=$(sed -n '1,200p' "$REL_SIM")
fi

STATUS_JSON="$OUT_DIR/status.json"
STATUS_SUMMARY=""
if [ -f "$STATUS_JSON" ]; then
  STATUS_SUMMARY=$(python3 - <<'PY'
import json,sys
d=json.load(open('.mcp/dashboard/status.json'))
weak=d.get('coverage',{}).get('weak') or []
near=d.get('coverage',{}).get('near') or []
print(f"weak={len(weak)} near={len(near)} min_module={d.get('coverage',{}).get('min_module')}")
PY
  )
fi

cat > "$REPORT" <<EOF
# Pre-release Checklist Report

- Status: $STATUS_SUMMARY
- Docker verify: $DOCKER_OK
- VS Code lcov gate (${LCOV_THRESHOLD}%): $LCOV_OK
- Release body: ${BODY_PATH}

## Release Simulation (auto)
${SIM_LINES}

EOF

echo "[pre-release] Report written: $REPORT"
echo "$REPORT"

