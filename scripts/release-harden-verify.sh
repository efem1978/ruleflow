#!/usr/bin/env bash
set -euo pipefail

echo "[release] enable license hard gate"
python3 -m mcp_rules_assistant.cli license-require-on >/dev/null

echo "[release] expect gated failure on ci.generate via MCP server"
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

echo "[release] disable license hard gate"
python3 -m mcp_rules_assistant.cli license-require-off >/dev/null
echo "[release] verification OK"

