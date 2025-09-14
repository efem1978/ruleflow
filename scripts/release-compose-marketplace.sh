#!/usr/bin/env bash
set -euo pipefail
OUT_DIR=".mcp/dashboard"
SNIP="$OUT_DIR/release_note_snippet.md"
CHG="$OUT_DIR/release_changes.md"
MARKET="$OUT_DIR/release_marketplace.md"
mkdir -p "$OUT_DIR"

ver=$(python3 - <<'PY'
import re
t=open('pyproject.toml','r',encoding='utf-8').read()
m=re.search(r"^version\s*=\s*\"([^\"]+)\"", t, re.M)
print(m.group(1) if m else 'unknown')
PY
)

{
  echo "# v$ver"
  echo
  echo "## Summary"
  if [ -f "$SNIP" ]; then
    sed -n '1,40p' "$SNIP"
  else
    echo "- Maintenance and verification updates."
  fi
  echo
  echo "## Changes"
  if [ -f "$CHG" ]; then
    sed -n '1,80p' "$CHG"
  else
    echo "- See repository changelog."
  fi
} > "$MARKET"

echo "$MARKET"

