#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VS_DIR="$ROOT_DIR/extensions/vscode"
REPORT="$ROOT_DIR/extensions/compat_report.json"

ok_compile=0
ok_tests=0
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
  if MCP_VSCODE_TEST_ARGS="" npm --prefix "$VS_DIR" test; then ok_tests=1; fi || true
fi

REPORT="$REPORT" engine_req="$engine_req" node_ver="$node_ver" ok_compile="$ok_compile" ok_tests="$ok_tests" \
python3 - <<'PY' || true
import json,os
rep=os.environ.get('REPORT')
d={
  'vscode_engine': os.environ.get('engine_req',''),
  'node': os.environ.get('node_ver',''),
  'compile_ok': os.environ.get('ok_compile','0')=='1',
  'tests_ok': os.environ.get('ok_tests','0')=='1',
}
open(rep,'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,indent=2))
print('[ide-compat] report ->', rep)
PY

exit 0
