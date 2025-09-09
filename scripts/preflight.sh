#!/usr/bin/env sh
set -e

echo "[preflight] scanning for banned patterns in docs..."
# status.js 需要精确匹配，避免误伤 status.json 等
PATTERN='docker-compose.yml|--serve|localhost:9000|index.html|status\\.js([^a-zA-Z]|$)'
if rg -n -e "$PATTERN" DEVELOPMENT.md docs README.md >/dev/null 2>&1; then
  echo "[preflight] banned pattern detected in docs; please fix" >&2
  rg -n -e "$PATTERN" DEVELOPMENT.md docs README.md || true
  exit 1
fi

echo "[preflight] validating compose.yml..."
if command -v docker >/dev/null 2>&1; then
  docker compose config -q || { echo "[preflight] compose validation failed" >&2; exit 1; }
else
  echo "[preflight] docker not found; skip compose validation"
fi

echo "[preflight] checking for tracked forbidden files (report-only)..."
FORBID_FILES="bad.py ok2.py ok.txt docs/b.txt cov.json cov_cli.json coverage.xml pytest-junit.xml extensions/vscode/*.vsix"
FOUND=0
for f in $FORBID_FILES; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    echo "[preflight] tracked forbidden file: $f"
    FOUND=$((FOUND+1))
  fi
done
if [ "$FOUND" -gt 0 ]; then
  echo "[preflight] found $FOUND tracked forbidden file(s). Consider removing from index:"
  echo "  git rm --cached -f $FORBID_FILES"
fi

echo "[preflight] upstream branch presence (report-only)..."
if [ -x scripts/git-upstream-check.sh ]; then
  if command -v bash >/dev/null 2>&1; then
    bash scripts/git-upstream-check.sh || true
  else
    sh scripts/git-upstream-check.sh || true
  fi
else
  echo "[preflight] scripts/git-upstream-check.sh not found; skip upstream check"
fi

echo "[preflight] compliance commitment presence (report-only)..."
if [ -f .mcp/compliance.md ]; then
  echo "[preflight] compliance.md exists"
else
  echo "[preflight] compliance.md missing (report-only). Generate with: mcp-rules-assistant compliance-commitment"
fi

echo "[preflight] running docs anchors tests..."
python3 -c "import importlib,sys; sys.exit(0 if importlib.util.find_spec('pytest') else 1)" >/dev/null 2>&1
if [ $? -eq 0 ]; then
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/docs/test_docs_anchors.py
else
  echo "[preflight] pytest not found; running lightweight anchors check" >&2
  python3 - <<'PY'
from pathlib import Path
def read(p):
  return Path(p).read_text(encoding='utf-8', errors='ignore')
ROOT = Path('.').resolve()
dev = read('DEVELOPMENT.md')
anchors = ['开发指南总览','快速索引','环境与运行','TDD 逐层推进计划','提交与门禁','无人值守','文档维护与同步']
missing = [a for a in anchors if a not in dev]
if missing:
  raise SystemExit(f"missing anchors in DEVELOPMENT.md: {missing}")
rd = read('README.md')
if 'DEVELOPMENT.md' not in rd:
  raise SystemExit('README missing DEVELOPMENT link')
aid = read('docs/AI_DEVELOPER_GUIDE.md')
if 'DEVELOPMENT.md' not in aid:
  raise SystemExit('AI_DEVELOPER_GUIDE missing DEVELOPMENT link')
hooks = read('docs/HOOKS.md')
if 'VS Code 无头测试（必跑项）' not in hooks:
  raise SystemExit('HOOKS missing VS Code required hint')
print('[preflight] lightweight anchors OK')
PY
fi

echo "[preflight] coverage policy snapshot (report-only when present)..."
if [ -f coverage.xml ]; then
  # Use module CLI to summarize and ensure weak==0
  PYTHONWARNINGS=ignore PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m mcp_rules_assistant.cli coverage-report --json > cov_cli.json || true
  python3 - <<'PY'
import json, sys
from pathlib import Path
p=Path('cov_cli.json')
if not p.exists():
    print('[preflight] coverage report not generated'); sys.exit(0)
try:
    d=json.loads(p.read_text(encoding='utf-8'))
except Exception:
    print('[preflight] coverage report parse error (non-blocking)'); sys.exit(0)
weak=d.get('weak') or []
if weak:
    print('[preflight] Coverage policy gate would fail. Weak files:')
    for w in weak:
        print(' -', w.get('file'), 'cov=', w.get('coverage'), '<', w.get('threshold'))
else:
    print('[preflight] Coverage policy snapshot OK (weak=0)')
PY
else
  echo "[preflight] coverage.xml missing; skip coverage snapshot"
fi

echo "[preflight] checking version consistency (pyproject vs __init__)..."
python3 - <<'PY'
import re, sys
from pathlib import Path

p = Path('pyproject.toml').read_text(encoding='utf-8', errors='ignore')
try:
    import tomllib  # type: ignore
    data = tomllib.loads(p)
    v1 = data.get('project', {}).get('version')
except Exception:
    m = re.search(r"(?m)^version\s*=\s*\"([^\"]+)\"", p)
    v1 = m.group(1) if m else None

q = Path('mcp_rules_assistant/__init__.py').read_text(encoding='utf-8', errors='ignore')
m2 = re.search(r"__version__\s*=\s*\"([^\"]+)\"", q)
v2 = m2.group(1) if m2 else None

if not v1 or not v2:
    print('[preflight] cannot read versions', v1, v2)
    sys.exit(1)
if v1 != v2:
    print(f"[preflight] version mismatch: pyproject={v1} __init__={v2}")
    sys.exit(1)
print(f"[preflight] version OK: {v1}")
PY

echo "[preflight] OK"
