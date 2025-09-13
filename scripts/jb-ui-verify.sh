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

# Optional: compiled rules & suggestions counts
python3 - << 'PY'
import json, sys, os
from pathlib import Path
root = Path(os.getcwd())
rc = root/'.mcp'/'rules_compiled.json'
if not rc.exists():
    print('[jb-ui-verify] rules_compiled.json missing (ok)')
    sys.exit(0)
try:
    D = json.loads(rc.read_text(encoding='utf-8'))
except Exception as e:
    print('[jb-ui-verify] WARN: parse rules_compiled.json failed:', e)
    sys.exit(0)
conf = D.get('conflicts') or []
sugg = D.get('suggestions') or []
print('[jb-ui-verify] rules: conflicts =', len(conf), 'suggestions =', len(sugg))
PY

# Optional: suggestions severity counters from markdown (if available)
python3 - << 'PY'
import re, os
from pathlib import Path
root = Path(os.getcwd())
md = root/'.mcp'/'rules_suggestions.md'
if not md.exists():
    print('[jb-ui-verify] suggestions(md): not found (ok)')
else:
    text = md.read_text(encoding='utf-8', errors='ignore')
    must = len(re.findall(r'(^|\n)\s*Severity\s*:\s*must\b', text, re.I))
    warn = len(re.findall(r'(^|\n)\s*Severity\s*:\s*warn\b', text, re.I))
    info = len(re.findall(r'(^|\n)\s*Severity\s*:\s*info\b', text, re.I))
    print(f"[jb-ui-verify] suggestions(md): must={must} warn={warn} info={info}")
PY

# Write consolidated JSON snapshot for artifacts
python3 - << 'PY'
import json, os
from pathlib import Path
root = Path(os.getcwd())
dash = root/'.mcp'/'dashboard'
out = {
  'plan': {},
  'coverage': {},
  'rules': {},
  'suggestions': {},
  'memory': {}
}
try:
  S = json.loads((dash/'status.json').read_text(encoding='utf-8'))
  out['plan'] = S.get('plan') or {}
  out['coverage']['weak_count'] = len(((S.get('coverage') or {}).get('weak') or []))
  out['coverage']['count'] = (S.get('coverage') or {}).get('count')
except Exception:
  pass
try:
  import json
  M = json.loads((root/'.mcp'/'memory.json').read_text(encoding='utf-8'))
  turns = M.get('turns') or []
  out['memory']['turns_count'] = len(turns)
  out['memory']['has_summary'] = bool((M.get('summary') or '').strip())
except Exception:
  pass
try:
  C = json.loads((dash/'coverage_summary.json').read_text(encoding='utf-8'))
  out['coverage']['weak'] = len(C.get('weak') or [])
  out['coverage']['near'] = len(C.get('near') or [])
  # TopN (up to 5) for quick glance
  weak = C.get('weak') or []
  near = C.get('near') or []
  def _fmt_w(it):
      try:
          return {
              'file': it.get('file',''),
              'coverage': round(float(it.get('coverage',0.0))*100, 1),
              'threshold': int(float(it.get('threshold',0.0))*100),
          }
      except Exception:
          return {'file': str(it)}
  out['coverage']['weak_top'] = list(map(_fmt_w, weak[:5]))
  out['coverage']['near_top'] = list(map(_fmt_w, near[:5]))
except Exception:
  pass
try:
  import csv
  gp = dash/'groups.csv'
  if gp.exists():
      rows = list(csv.DictReader(gp.open('r', encoding='utf-8')))
      # Normalize and sort by weak_count desc
      norm = []
      for r in rows:
          try:
              cov = round(float(r.get('coverage',0.0))*100,1)
              thr = int(float(r.get('threshold',0.0))*100)
              wk = int(r.get('weak_count',0) or 0)
              fc = int(r.get('files_count',0) or 0)
              norm.append({'prefix': r.get('prefix',''), 'coverage': cov, 'threshold': thr, 'weak': wk, 'files': fc})
          except Exception:
              pass
      norm.sort(key=lambda x: x.get('weak',0), reverse=True)
      out.setdefault('coverage',{})['groups_top'] = norm[:5]
      # Write markdown table (top 10)
      md_lines = ['| prefix | coverage | threshold | weak/files |', '|---|---:|---:|---:|']
      for g in norm[:10]:
          md_lines.append(f"| {g['prefix']} | {g['coverage']:.1f}% | {g['threshold']}% | {g['weak']}/{g['files']} |")
      (dash/'jb_groups.md').write_text('\n'.join(md_lines), encoding='utf-8')
except Exception:
  pass
try:
  RC = json.loads((root/'.mcp'/'rules_compiled.json').read_text(encoding='utf-8'))
  out['rules']['conflicts'] = len(RC.get('conflicts') or [])
  out['rules']['suggestions'] = len(RC.get('suggestions') or [])
except Exception:
  pass
try:
  import re
  text = (root/'.mcp'/'rules_suggestions.md').read_text(encoding='utf-8')
  out['suggestions']['must'] = len(re.findall(r'(^|\n)\s*Severity\s*:\s*must\b', text, re.I))
  out['suggestions']['warn'] = len(re.findall(r'(^|\n)\s*Severity\s*:\s*warn\b', text, re.I))
  out['suggestions']['info'] = len(re.findall(r'(^|\n)\s*Severity\s*:\s*info\b', text, re.I))
except Exception:
  pass
dash.mkdir(parents=True, exist_ok=True)
(dash/'jb_verify.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print('[jb-ui-verify] wrote', dash/'jb_verify.json')
PY

echo "[jb-ui-verify] done"

# Append execution/CI snapshot from assistant.yaml (best-effort)
python3 - << 'PY'
import json
from pathlib import Path
root = Path('.')
dash = root/'.mcp'/'dashboard'
assist = root/'.mcp'/'assistant.yaml'
outp = dash/'jb_verify.json'
try:
    out = json.loads(outp.read_text(encoding='utf-8'))
except Exception:
    out = {}
ex = {}
ci = {}
try:
    txt = assist.read_text(encoding='utf-8')
    def find_bool(key: str) -> bool|None:
        for line in txt.splitlines():
            if key in line:
                if any(t in line for t in (': true', ': True', ': 1')):
                    return True
                if any(t in line for t in (': false', ': False', ': 0')):
                    return False
        return None
    ex['fs_guard_post_checks'] = find_bool('fs_guard_post_checks')
    ex['fs_guard_strict'] = find_bool('fs_guard_strict')
    ex['checks_delegate_run_cmd'] = find_bool('checks_delegate_run_cmd')
    ci['hadolint'] = find_bool('hadolint:')
    ci['vscode_required'] = find_bool('vscode_required')
    ci['mutation_gate_strict'] = find_bool('mutation_gate_strict')
    # semgrep_config: try to read string value
    sem = None
    for line in txt.splitlines():
        if 'semgrep_config:' in line:
            sem = line.split(':',1)[1].strip().strip('"')
            break
    if sem:
        ci['semgrep_config'] = sem
except Exception:
    pass
out['execution'] = ex
out['ci'] = ci
dash.mkdir(parents=True, exist_ok=True)
outp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print('[jb-ui-verify] exec/ci snapshot appended to', outp)
PY

# Roundtrip: toggle execution.fs_guard_* flags in assistant.yaml (best-effort, no YAML deps)
python3 - << 'PY'
from pathlib import Path
import re
root = Path('.')
assist = root/'.mcp'/'assistant.yaml'
assist.parent.mkdir(parents=True, exist_ok=True)
text = ''
if assist.exists():
    text = assist.read_text(encoding='utf-8')
if not text.strip():
    text = 'execution:\n  fs_guard_post_checks: true\n  fs_guard_strict: true\n'

def set_or_flip(s: str, key: str) -> str:
    # if key exists, flip true<->false; else insert under execution:
    pat = re.compile(rf'^(\s*){re.escape(key)}\s*:\s*(true|false)\s*$', re.M)
    m = pat.search(s)
    if m:
        indent = m.group(1)
        val = m.group(2)
        new = 'false' if val.lower() == 'true' else 'true'
        return s[:m.start()] + f"{indent}{key}: {new}" + s[m.end():]
    # ensure execution: block exists
    if 'execution:' not in s:
        s += '\nexecution:\n'
    # find execution: line and its indent
    em = re.search(r'^(\s*)execution:\s*$', s, re.M)
    if em:
        indent = em.group(1) + '  '
        insert_pos = em.end()
        return s[:insert_pos] + f"\n{indent}{key}: true" + s[insert_pos:]
    return s + f"\n{key}: true\n"

text = set_or_flip(text, 'fs_guard_post_checks')
text = set_or_flip(text, 'fs_guard_strict')
assist.write_text(text, encoding='utf-8')
print('[jb-ui-verify] toggled fs_guard_* in assistant.yaml')
PY
