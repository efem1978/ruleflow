#!/usr/bin/env bash
set -euo pipefail
# Remove workspace-isolated copies of the RuleFlow extension and user-data.

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[WS Purge] Removing workspace isolated dirs under .mcp/ ..."
rm -rf "${WS_ROOT}/.mcp/vscode-extensions" \
       "${WS_ROOT}/.mcp/vscode-user" \
       "${WS_ROOT}/.mcp/cursor-extensions" \
       "${WS_ROOT}/.mcp/cursor-user" || true

echo "[WS Purge] Cleaning dashboard sentinels/logs ..."
rm -f "${WS_ROOT}/.mcp/dashboard/fake_mode" \
      "${WS_ROOT}/.mcp/dashboard/panel_auto_open_once" \
      "${WS_ROOT}/.mcp/dashboard/server.log" || true

echo "[WS Purge] Done. Please fully quit VS Code & Cursor (Cmd+Q) and relaunch."

