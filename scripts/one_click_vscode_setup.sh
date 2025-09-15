#!/usr/bin/env bash
set -euo pipefail

# One‑click setup for RuleFlow in this workspace (VS Code only)
# - Creates local venv under .mcp/venv and installs the MCP server (editable)
# - Installs the VS Code extension from the packaged VSIX
# - Launches VS Code on this workspace

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VSIX_PATH="${WS_ROOT}/extensions/vscode/mcp-rules-assistant-0.2.5.vsix"

# Prefer explicit VS Code CLI and avoid Cursor alias
VSCODE_BIN_DEFAULT='/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
CODE_BIN="${VSCODE_BIN:-${VSCODE_BIN_DEFAULT}}"

if [[ ! -x "${CODE_BIN}" ]]; then
  echo "ERROR: VS Code CLI not found at ${CODE_BIN}. Set VSCODE_BIN and retry." >&2
  exit 1
fi

if [[ ! -f "${VSIX_PATH}" ]]; then
  echo "ERROR: VSIX not found at ${VSIX_PATH}" >&2
  exit 2
fi

echo "[1/3] Prepare local venv and install MCP server"
python3 -m venv "${WS_ROOT}/.mcp/venv"
"${WS_ROOT}/.mcp/venv/bin/python" -m pip install -U pip setuptools wheel >/dev/null
"${WS_ROOT}/.mcp/venv/bin/python" -m pip install -e "${WS_ROOT}" >/dev/null

echo "[2/3] Install VS Code extension into your normal profile"
"${CODE_BIN}" --uninstall-extension ruleflow.mcp-rules-assistant >/dev/null 2>&1 || true
"${CODE_BIN}" --install-extension "${VSIX_PATH}" --force >/dev/null

echo "[3/3] Launch VS Code on this workspace"
"${CODE_BIN}" "${WS_ROOT}" >/dev/null 2>&1 || true

echo "Done. Status bar should show 'RuleFlow' in VS Code."

