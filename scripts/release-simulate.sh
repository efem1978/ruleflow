#!/usr/bin/env bash
# Local release simulation (no remote push)
# Produces a markdown report at .mcp/dashboard/release_check.md

set -u

OUT_DIR=".mcp/dashboard"
REPORT="$OUT_DIR/release_check.md"
mkdir -p "$OUT_DIR"

ok() { echo "OK"; }
fail() { echo "FAIL"; }
skip() { echo "SKIPPED"; }

PY_OK=$(skip)
COV_OK=$(skip)
FRONTEND_OK=$(skip)
LIC_OK=$(skip)
PKG_OK=$(skip)

echo "[rel-sim] Running Python tests + coverage..."
if command -v python3 >/dev/null 2>&1; then
  if PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml; then
    PY_OK=$(ok)
  else
    PY_OK=$(fail)
  fi
else
  PY_OK=$(skip)
fi

echo "[rel-sim] Checking coverage weak files..."
if command -v python3 >/dev/null 2>&1; then
  if python3 -m mcp_rules_assistant.cli coverage-report --json > "$OUT_DIR/cov.json" 2>/dev/null; then
    if python3 - <<'PY'
import json,sys
d=json.load(open('.mcp/dashboard/cov.json'))
w=d.get('weak') or []
sys.exit(1 if w else 0)
PY
    then COV_OK=$(ok); else COV_OK=$(fail); fi
  else
    COV_OK=$(skip)
  fi
else
  COV_OK=$(skip)
fi

echo "[rel-sim] VS Code compile + test + coverage gate (80%)..."
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  if npm --prefix extensions/vscode run compile >/dev/null 2>&1; then :; fi
  # execute tests best-effort; allow failure but still evaluate lcov if present
  if [ -n "${MCP_VSCODE_TEST_ARGS:-}" ]; then
    npm --prefix extensions/vscode test || true
  else
    MCP_VSCODE_TEST_ARGS="" npm --prefix extensions/vscode test || true
  fi
  if [ -f extensions/vscode/coverage/lcov.info ]; then
    if sh scripts/check-lcov.sh extensions/vscode/coverage/lcov.info 80 gate; then
      FRONTEND_OK=$(ok)
    else
      FRONTEND_OK=$(fail)
    fi
  else
    FRONTEND_OK=$(skip)
  fi
else
  FRONTEND_OK=$(skip)
fi

echo "[rel-sim] License harden verify..."
if sh scripts/release-harden-verify.sh >/dev/null 2>&1; then
  LIC_OK=$(ok)
else
  LIC_OK=$(fail)
fi

echo "[rel-sim] Build Python package + twine check..."
if command -v python3 >/dev/null 2>&1; then
  python3 -m pip -q install --upgrade build twine >/dev/null 2>&1 || true
  if python3 -m build >/dev/null 2>&1 && python3 -m twine check dist/* >/dev/null 2>&1; then
    PKG_OK=$(ok)
  else
    PKG_OK=$(fail)
  fi
else
  PKG_OK=$(skip)
fi

cat > "$REPORT" <<EOF
# Release Simulation Report

- Python tests + coverage: $PY_OK
- Coverage weak files (policy): $COV_OK
- VS Code lcov gate (80%): $FRONTEND_OK
- License harden verify: $LIC_OK
- Python package build + twine check: $PKG_OK

Artifacts:
- Coverage JSON: ".mcp/dashboard/cov.json" (if generated)
- Report time: $(date -u +'%Y-%m-%dT%H:%M:%SZ')

Notes:
- VS Code tests are best-effort; in headless/CI they run under xvfb. Threshold can be adjusted in CI.
- License harden verify toggles project config on/off; it does not leave license required enabled.
EOF

echo "[rel-sim] Report written to $REPORT"

