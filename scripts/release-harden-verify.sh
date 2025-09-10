#!/usr/bin/env sh
set -eu

echo "[release] enable license hard gate"
REPORT=".mcp/dashboard/release_check.md"
mkdir -p .mcp/dashboard
{
  echo "# Release Harden Verify"
  echo
  echo "Start: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo
} > "$REPORT"
python3 -m mcp_rules_assistant.cli license-require-on >/dev/null

echo "[release] expect gated failure on ci.generate via MCP server"
echo "- Gate check: expect failure on ci.generate (license required)" >> "$REPORT"
# Temporarily disable any existing license to ensure gate triggers
BACKUP_DIR=".mcp/.release_verify_bak"
mkdir -p "$BACKUP_DIR"
RESTORE_FILE="$BACKUP_DIR/restore_list.txt"
rm -f "$RESTORE_FILE"
for P in "$HOME/.mcp/license.json" ".mcp/license.json"; do
  if [ -f "$P" ]; then
    B="$BACKUP_DIR/$(echo "$P" | tr '/' '_')"
    mv "$P" "$B"
    echo "$P:$B" >> "$RESTORE_FILE"
  fi
done

python3 - <<'PY'
from mcp_rules_assistant.mcp_server import JsonRpcServer
srv = JsonRpcServer()
try:
    srv._call_tool("ci.generate", {})
except Exception as e:
    msg = str(e)
    if "license required" in msg or "license" in msg:
        print("[release] gate OK:", msg)
    else:
        raise
else:
    raise SystemExit("gate not enforced (unexpected success)")
PY

echo "- Result: gate OK (ci.generate denied without license)" >> "$REPORT"

# Restore any license files
if [ -f "$RESTORE_FILE" ]; then
  while IFS= read -r it; do
    P="${it%%:*}"
    B="${it#*:}"
    mv "$B" "$P" || true
  done < "$RESTORE_FILE"
fi

echo "[release] disable license hard gate"
python3 -m mcp_rules_assistant.cli license-require-off >/dev/null
echo "[release] verification OK"
{
  echo
  echo "End: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
} >> "$REPORT"
