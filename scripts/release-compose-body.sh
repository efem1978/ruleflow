#!/usr/bin/env bash
set -euo pipefail
OUT_DIR=".mcp/dashboard"
SNIP="$OUT_DIR/release_note_snippet.md"
CHG="$OUT_DIR/release_changes.md"
BODY="$OUT_DIR/release_body.md"
mkdir -p "$OUT_DIR"

# Ensure snippet and changes exist (best-effort)
python3 scripts/release-note-from-report.py --report "$OUT_DIR/release_check.md" --out "$SNIP" || true
python3 scripts/release-changes-from-git.py || true

ver=$(python3 - <<'PY'
import re
t=open('pyproject.toml','r',encoding='utf-8').read()
m=re.search(r"^version\s*=\s*\"([^\"]+)\"", t, re.M)
print(m.group(1) if m else 'unknown')
PY
)

{
  echo "# Release $ver"
  echo
  if [ -f docs/RELEASE_NOTES_TEMPLATE.md ]; then
    cat docs/RELEASE_NOTES_TEMPLATE.md
    echo
  fi
  if [ -f "$SNIP" ]; then
    echo '---'
    echo 'Auto Report'
    echo
    cat "$SNIP"
  fi
  if [ -f "$CHG" ]; then
    echo '---'
    echo 'Changes (auto from git)'
    echo
    cat "$CHG"
  fi
} > "$BODY"

echo "$BODY"

