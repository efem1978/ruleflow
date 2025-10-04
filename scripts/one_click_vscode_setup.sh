#!/usr/bin/env bash
set -euo pipefail

# One‑click setup for RuleFlow in this workspace (VS Code only)
# - Creates local venv under .mcp/venv and installs the MCP server (editable)
# - Installs the VS Code extension from the packaged VSIX
# - Launches VS Code on this workspace

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VSIX_DIR="${WS_ROOT}/extensions/vscode"

# Prefer explicit VS Code CLI and avoid Cursor alias; fallback to open on macOS
VSCODE_BIN_DEFAULT='/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'
CODE_BIN="${VSCODE_BIN:-${VSCODE_BIN_DEFAULT}}"
OS_NAME="$(uname -s 2>/dev/null || echo unknown)"

# Always (re)build VSIX to include latest source changes
echo "[one-click] Building VSIX..."
pushd "${VSIX_DIR}" >/dev/null
npm --version >/dev/null 2>&1 || { echo "ERROR: npm not found in PATH" >&2; popd >/dev/null; exit 2; }
# Remove stale VSIX artifacts to avoid picking an older file by name sorting
rm -f mcp-rules-assistant-*.vsix 2>/dev/null || true
npm install
npm run compile
npm run package
# Pick latest packaged VSIX dynamically
VSIX_FILE="$(ls -1 mcp-rules-assistant-*.vsix 2>/dev/null | sort -V | tail -n1)"
if [[ -z "${VSIX_FILE}" ]]; then
  echo "ERROR: No VSIX produced under ${VSIX_DIR}." >&2
  popd >/dev/null
  exit 2
fi
VSIX_PATH="${VSIX_DIR}/${VSIX_FILE}"
popd >/dev/null

echo "[1/3] Prepare local venv and install MCP server"
python3 -m venv "${WS_ROOT}/.mcp/venv"
"${WS_ROOT}/.mcp/venv/bin/python" -m pip install -U pip setuptools wheel >/dev/null
"${WS_ROOT}/.mcp/venv/bin/python" -m pip install -e "${WS_ROOT}" >/dev/null

echo "[2/3] Install VS Code extension into your normal profile (${VSIX_FILE})"
# Best-effort purge via helper if available
if [[ -f "${WS_ROOT}/scripts/purge_ruleflow_extensions.sh" ]]; then
  bash "${WS_ROOT}/scripts/purge_ruleflow_extensions.sh" || true
fi

if [[ -x "${CODE_BIN}" ]]; then
  "${CODE_BIN}" --install-extension "${VSIX_PATH}" --force >/dev/null || true
else
  if [[ "${OS_NAME}" == "Darwin" ]]; then
    echo "[one-click] VS Code CLI not found; opening VSIX with Visual Studio Code (confirm install in GUI if prompted)."
    open -a "Visual Studio Code" "${VSIX_PATH}" || true
  else
    echo "WARN: VS Code CLI not found and no GUI fallback on this OS. Please install VSIX manually: ${VSIX_PATH}" >&2
  fi
fi

echo "[3/3] Launch VS Code on this workspace"
if [[ -x "${CODE_BIN}" ]]; then
  "${CODE_BIN}" "${WS_ROOT}" >/dev/null 2>&1 || true
elif [[ "${OS_NAME}" == "Darwin" ]]; then
  open -a "Visual Studio Code" "${WS_ROOT}" || true
fi

echo "Done. Status bar should show 'RuleFlow' in VS Code."

# Diagnostics (best-effort)
if [[ -f "${WS_ROOT}/scripts/diagnose-env.sh" ]]; then
  echo "[one-click] Running environment diagnostics..."
  bash "${WS_ROOT}/scripts/diagnose-env.sh" || true
  echo "[one-click] Report: ${WS_ROOT}/.mcp/dashboard/install_report.md"
fi

echo "[one-click] Latest VSIX: ${VSIX_PATH}"

