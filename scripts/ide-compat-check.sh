#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VS_DIR="$ROOT_DIR/extensions/vscode"
REPORT="$ROOT_DIR/extensions/compat_report.json"

ok_compile=0
ok_tests=0
note=""
tests_status="unknown"
vsix_ok=0
vsix_path=""
cursor_hint=""
windsurf_hint=""
node_ver=""
engine_req=""

if command -v node >/dev/null 2>&1; then
  node_ver="$(node -v 2>/dev/null || true)"
fi

# Extract VS Code engine requirement from package.json
engine_req=$(VS_DIR="$VS_DIR" python3 - <<'PY' 2>/dev/null || true
import json,sys,os
p=os.path.join(os.environ.get('VS_DIR',''), 'package.json')
try:
  d=json.load(open(p,encoding='utf-8'))
  print(d.get('engines',{}).get('vscode',''))
except Exception:
  pass
PY
)

echo "[ide-compat] VS Code engine: ${engine_req:-unknown}"
echo "[ide-compat] Node version: ${node_ver:-missing}"

if [ -d "$VS_DIR" ]; then
  echo "[ide-compat] compiling VS Code extension..."
  if npm --prefix "$VS_DIR" run compile; then ok_compile=1; fi
  echo "[ide-compat] running headless tests (best-effort)..."
  if MCP_VSCODE_TEST_ARGS="" npm --prefix "$VS_DIR" test; then
    ok_tests=1
  else
    # Provide quick hints for macOS headless runs
    if [ "$(uname -s 2>/dev/null || echo unknown)" = "Darwin" ]; then
      note=$'vscode-test may require GUI/flags on macOS. Try:\n  export MCP_VSCODE_TEST_ARGS=""\n  npm --prefix extensions/vscode test\nSee docs/VS_CODE_TEST.md'
    else
      note="vscode-test may require GUI/flags on this OS; see docs/VS_CODE_TEST.md"
    fi
  fi || true

  # Try packaging VSIX (best-effort)
  if npm --prefix "$VS_DIR" run package >/dev/null 2>&1; then
    latest_vsix="$(ls -t "$VS_DIR"/*.vsix 2>/dev/null | head -n 1 || true)"
    if [ -n "$latest_vsix" ]; then vsix_ok=1; vsix_path="$latest_vsix"; fi
  else
    if [ -z "$note" ]; then note="VSIX package may require 'vsce' devDependency install"; else note="$note; VSIX package may require 'vsce' install"; fi
  fi
fi

if [ "$vsix_ok" = "1" ]; then
  cursor_hint=$'Cursor: 打开 Extensions → Install from VSIX... → 选择 VSIX 文件'
  windsurf_hint=$'Windsurf: 打开 Extensions → Install from VSIX... → 选择 VSIX 文件'
fi

# Derive tests_status (ok / skipped / fail)
uname_s="$(uname -s 2>/dev/null || echo unknown)"
if [ "$ok_tests" = "1" ]; then
  tests_status="ok"
else
  if [ "$uname_s" = "Darwin" ]; then
    tests_status="skipped"
  else
    tests_status="fail"
  fi
fi

REPORT="$REPORT" engine_req="$engine_req" node_ver="$node_ver" ok_compile="$ok_compile" ok_tests="$ok_tests" tests_status="$tests_status" note="$note" vsix_ok="$vsix_ok" vsix_path="$vsix_path" cursor_hint="$cursor_hint" windsurf_hint="$windsurf_hint" \
python3 - <<'PY' || true
import json,os
rep=os.environ.get('REPORT')
d={
  'vscode_engine': os.environ.get('engine_req',''),
  'node': os.environ.get('node_ver',''),
  'compile_ok': os.environ.get('ok_compile','0')=='1',
  'tests_ok': os.environ.get('ok_tests','0')=='1',
  'tests_status': os.environ.get('tests_status','unknown'),
  'vsix_ok': os.environ.get('vsix_ok','0')=='1',
  'vsix': os.environ.get('vsix_path',''),
  'cursor_install_hint': os.environ.get('cursor_hint',''),
  'windsurf_install_hint': os.environ.get('windsurf_hint',''),
  'note': os.environ.get('note',''),
}
open(rep,'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,indent=2))
print('[ide-compat] report ->', rep)
PY

exit 0
