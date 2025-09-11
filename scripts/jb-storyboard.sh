#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="extensions/jetbrains/screenshots"
mkdir -p "$OUT_DIR"

echo "[jb-storyboard] generating coverage report JSON ..."
if python3 -m mcp_rules_assistant.cli coverage-report --json > "$OUT_DIR/jb_coverage_report.json" 2>/dev/null; then
  :
else
  echo "[jb-storyboard] WARN: coverage-report failed (no coverage.xml?). Skipping." >&2
fi

echo "[jb-storyboard] copying plan markdown ..."
if [ -f .mcp/plan.md ]; then
  cp -f .mcp/plan.md "$OUT_DIR/jb_plan.md"
else
  echo "[jb-storyboard] WARN: .mcp/plan.md not found; run: mcp-rules-assistant plan-init" >&2
fi

echo "[jb-storyboard] dumping memory snapshot JSON ..."
python3 - "$OUT_DIR" <<'PY'
import json, sys
from pathlib import Path
from mcp_rules_assistant.memory import MemoryManager
mm = MemoryManager(Path('.'))
out = mm.snapshot()
Path(sys.argv[1]).joinpath('jb_memory.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8'
)
PY

# copy compiled rules & suggestions if present
if [ -f .mcp/rules_compiled.json ]; then
  cp -f .mcp/rules_compiled.json "$OUT_DIR/jb_rules_compiled.json"
fi
if [ -f .mcp/rules_suggestions.md ]; then
  cp -f .mcp/rules_suggestions.md "$OUT_DIR/jb_rules_suggestions.md"
fi

echo "[jb-storyboard] simulating fs.apply_patch (dry-run, strict) ..."
python3 - "$OUT_DIR" <<'PY'
import json, sys
from mcp_rules_assistant.mcp_server import JsonRpcServer
srv = JsonRpcServer()
args = {
    "files": [
        {"path": "docs/jb_demo.md", "content": "Demo from storyboard\n"}
    ],
    "dryRun": True,
    "strict": True,
}
res = srv._call_tool("fs.apply_patch", args)
Path = __import__('pathlib').Path
Path(sys.argv[1]).joinpath('jb_fs_apply_patch_dry.json').write_text(
    json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8'
)
PY

echo "[jb-storyboard] done. Outputs in $OUT_DIR"
