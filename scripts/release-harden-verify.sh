#!/usr/bin/env bash
set -euo pipefail

echo "[release] enable license hard gate"
python3 -m mcp_rules_assistant.cli license-require-on >/dev/null

echo "[release] expect gated failure on ci.generate via MCP server"
# Temporarily disable any existing license to ensure gate triggers
BACKUP_DIR=".mcp/.release_verify_bak"
mkdir -p "$BACKUP_DIR"
RESTORE_LIST=()
for P in "$HOME/.mcp/license.json" ".mcp/license.json"; do
  if [ -f "$P" ]; then
    B="$BACKUP_DIR/$(echo "$P" | tr '/' '_')"
    mv "$P" "$B"
    RESTORE_LIST+=("$P:$B")
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

# Restore any license files
for it in "${RESTORE_LIST[@]}"; do
  P="${it%%:*}"
  B="${it##*:}"
  mv "$B" "$P"
done

echo "[release] disable license hard gate"
python3 -m mcp_rules_assistant.cli license-require-off >/dev/null
echo "[release] verification OK"
