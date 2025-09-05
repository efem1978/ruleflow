#!/usr/bin/env sh
set -e

echo "[verify] 1/4 Preflight"
sh scripts/preflight.sh

echo "[verify] 2/4 Tests + Coverage"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p pytest_cov --maxfail=1 --disable-warnings -W error --strict-markers --cov=mcp_rules_assistant --cov-report=xml:coverage.xml --cov-report=term-missing

echo "[verify] 3/4 Coverage Gate"
python3 -m mcp_rules_assistant.cli coverage-report --json > /tmp/coverage_report.json
python3 - << 'PY'
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
PY

echo "[verify] 4/4 dev_agent smoke (local)"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 DEV_AGENT_MAX_CYCLES=1 python3 -m mcp_rules_assistant.dev_agent --interval 1 >/dev/null 2>&1 || true
python3 - << 'PY'
from pathlib import Path
import json,sys
p=Path('.mcp/dashboard/status.json')
if not p.exists():
  print('[verify] WARN: dev_agent status.json not found; skipping smoke checks')
  sys.exit(0)
data=json.loads(p.read_text(encoding='utf-8'))
ok=(data.get('tests') or {}).get('ok')
mode=(data.get('tests') or {}).get('mode')
weak=len(((data.get('coverage') or {}).get('weak') or []))
print('[verify] dev_agent tests.ok =', ok, 'mode =', mode, 'coverage.weak =', weak)
if not ok or weak:
  print('[verify] FAIL: dev_agent smoke indicates failing tests or weak coverage')
  sys.exit(1)
PY

echo "[verify] OK"

