#!/usr/bin/env bash
set -euo pipefail

# Install the packaged VSIX into the current VS Code remote host (Dev Container/WSL/SSH)
# Usage: scripts/install-remote-vsix.sh [VSIX_PATH]

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VSIX_PATH="${1:-${WS_ROOT}/extensions/vscode/mcp-rules-assistant-0.2.7.vsix}"

if [[ ! -f "${VSIX_PATH}" ]]; then
  echo "[remote-vsix] VSIX not found: ${VSIX_PATH}" >&2
  exit 2
fi

# Prefer using VS Code command to install into remote host if available.
# This works inside remote windows and will install to the remote extension host.
if command -v code >/dev/null 2>&1; then
  echo "[remote-vsix] Installing via 'code --install-extension' to current window target"
  code --install-extension "${VSIX_PATH}" --force || true
  exit 0
fi

# Fallback: write VSIX into workspace .mcp/ide and ask VS Code to install it via command (when possible)
IDE_DIR="${WS_ROOT}/.mcp/ide"
mkdir -p "${IDE_DIR}"
TARGET_VSIX="${IDE_DIR}/$(basename "${VSIX_PATH}")"
cp -f "${VSIX_PATH}" "${TARGET_VSIX}"
echo "[remote-vsix] Copied VSIX to ${TARGET_VSIX}. If VS Code is open remotely, run:"
echo "[remote-vsix]  - Workbench: Install Extension (select ${TARGET_VSIX})"
exit 0






