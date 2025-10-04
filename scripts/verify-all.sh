#!/usr/bin/env bash
set -e

echo "[verify] 1/4 Preflight"
sh scripts/preflight.sh

echo "[verify] 2/4 Tests + Coverage"
# Prefer project venv Python if available for consistency
PY=python3
if [ -x ".mcp/venv/bin/python" ]; then
  # Use venv python only if it is executable and works in current OS
  if ./.mcp/venv/bin/python - <<'PY' >/dev/null 2>&1
import sys
print('ok')
PY
  then
    PY=".mcp/venv/bin/python"
  fi
fi
# Ensure venv console-scripts are discoverable by PATH for subprocess calls inside tests
if [ -d ".mcp/venv/bin" ]; then
  export PATH="$(pwd)/.mcp/venv/bin:$PATH"
fi

# Quiet mode (optional): set VERIFY_QUIET=1 for extra-silent pytest (-qq)
PYTEST_Q="-q"
if [ "${VERIFY_QUIET:-0}" = "1" ]; then
  PYTEST_Q="-qq"
fi

# Ensure required test plugins are installed (benchmark, psutil)
"$PY" -m pip install -U pytest-benchmark psutil >/dev/null 2>&1 || true
if [ "${COVERAGE_WARN_FILTER:-0}" = "1" ] && [ -x scripts/coverage-warn-filter.sh ]; then
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PY" -m pytest $PYTEST_Q -p pytest_cov -p pytest_benchmark.plugin --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml --cov-report=term-missing --junitxml=pytest-junit.xml 2> >(bash scripts/coverage-warn-filter.sh 1>&2)
else
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$PY" -m pytest $PYTEST_Q -p pytest_cov -p pytest_benchmark.plugin --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml --cov-report=term-missing --junitxml=pytest-junit.xml
fi

echo "[verify] Skip/XFail Summary (non-blocking)"
"$PY" scripts/pytest-skipxfail-summary.py pytest-junit.xml || true

echo "[verify] 3/4 Coverage Gate"
"$PY" -m mcp_rules_assistant.cli coverage-report --json > /tmp/coverage_report.json
"$PY" - << 'PY'
import json,sys
D=json.load(open('/tmp/coverage_report.json'))
weak=D.get('weak') or []
groups=D.get('groups') or []
near=D.get('near') or []
print('[verify] weak_count =', len(weak))
for g in groups:
  print('[verify] group', g.get('prefix'), 'cov=', round(g.get('coverage',0)*100,2),'%','>=', int(g.get('threshold',0)*100),'%','weak', g.get('weak_count'), '/', g.get('files_count'))
print('[verify] near_count =', len(near))
if weak:
  print('[verify] FAIL: coverage weak files present')
  sys.exit(1)
if near:
  top = near[:5]
  print('[verify] near top5:')
  for it in top:
    print(' -', f"{round((it.get('coverage',0)*100),1)}% ≥ {int((it.get('threshold',0))*100)}% —", it.get('file',''))
PY

echo "[verify] Coverage Export (CSV/JSON)"
"$PY" -m mcp_rules_assistant.cli coverage-export --out-dir .mcp/dashboard --weak-top 50 --near-top 50 --within 3 || true

echo "[verify] 4/4 dev_agent smoke (local)"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 DEV_AGENT_MAX_CYCLES=1 "$PY" -m mcp_rules_assistant.dev_agent --interval 1 >/dev/null 2>&1 || true
"$PY" - << 'PY'
from pathlib import Path
import json,sys,os
p=Path('.mcp/dashboard/status.json')
if not p.exists():
  print('[verify] WARN: dev_agent status.json not found; skipping smoke checks')
  sys.exit(0)
data=json.loads(p.read_text(encoding='utf-8'))
ok=(data.get('tests') or {}).get('ok')
mode=(data.get('tests') or {}).get('mode')
weak=len(((data.get('coverage') or {}).get('weak') or []))
print('[verify] dev_agent tests.ok =', ok, 'mode =', mode, 'coverage.weak =', weak)
strict = os.environ.get('VERIFY_DEV_AGENT_STRICT','0') in ('1','true','True')
if (not ok or weak) and strict:
  print('[verify] FAIL: dev_agent smoke indicates failing tests or weak coverage (strict mode)')
  sys.exit(1)
if not ok:
  print('[verify] WARN: dev_agent tests.ok is False (non-blocking)')
if weak:
  print('[verify] WARN: dev_agent coverage has weak files =', weak, '(non-blocking)')
PY

echo "[verify] JetBrains UI verify (optional)"
bash scripts/jb-ui-verify.sh || true
if [ -f .mcp/dashboard/jb_verify.json ]; then
  echo "[verify] jb_verify.json summary:" && head -n 50 .mcp/dashboard/jb_verify.json || true
fi
if [ -f .mcp/dashboard/jb_groups.md ]; then
  echo "[verify] jb_groups.md (Top 10):" && head -n 20 .mcp/dashboard/jb_groups.md || true
fi

echo "[verify] Suggestions (tuning guide)"
python3 - << 'PY'
import json, os
from pathlib import Path
root=Path('.')
dash=root/'.mcp'/'dashboard'
p = dash/'jb_verify.json'
if not p.exists():
    print('[verify] jb_verify.json not found; run jb-ui-verify.sh')
else:
    D=json.loads(p.read_text(encoding='utf-8'))
    groups = (D.get('coverage') or {}).get('groups_top') or []
    near = (D.get('coverage') or {}).get('near_top') or []
    if groups:
        print('[verify] 建议：为以下前缀考虑分层阈值或集中补测（按弱项数降序）')
        for g in groups:
            print(' -', g.get('prefix',''), f"cov={g.get('coverage',0)}% th={g.get('threshold',0)}% weak={g.get('weak',0)}/{g.get('files',0)}")
    if near:
        print('[verify] 建议：优先补齐以下 nearTop 文件（微调即可达标）')
        for n in near:
            print(' -', n.get('file',''), f"cov={n.get('coverage',0)}% th={n.get('threshold',0)}%")
PY

echo "[verify] OK"
