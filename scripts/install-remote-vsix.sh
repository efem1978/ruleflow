#!/usr/bin/env bash
set -euo pipefail

# Install the packaged VSIX into the current VS Code remote host (Dev Container/WSL/SSH)
# Usage: scripts/install-remote-vsix.sh [VSIX_PATH]

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Auto-detect latest VSIX if not provided
if [[ -n "${1-}" ]]; then
  VSIX_PATH="$1"
else
  # Search both extension build dir and artifacts dir
  CANDIDATE=""
  if ls -1 "${WS_ROOT}/extensions/vscode"/mcp-rules-assistant-*.vsix >/dev/null 2>&1; then
    CANDIDATE="$(ls -1 "${WS_ROOT}/extensions/vscode"/mcp-rules-assistant-*.vsix | sort -V | tail -n1)"
  fi
  if ls -1 "${WS_ROOT}/extensions/artifacts"/mcp-rules-assistant-*.vsix >/dev/null 2>&1; then
    ART_LAST="$(ls -1 "${WS_ROOT}/extensions/artifacts"/mcp-rules-assistant-*.vsix | sort -V | tail -n1)"
    # Prefer artifacts dir if newer
    if [[ -z "${CANDIDATE}" ]]; then
      CANDIDATE="${ART_LAST}"
    else
      # Compare by version-sort order
      NEWER="$(printf '%s\n%s\n' "${CANDIDATE}" "${ART_LAST}" | sort -V | tail -n1)"
      CANDIDATE="${NEWER}"
    fi
  fi
  VSIX_PATH="${CANDIDATE}"
fi

if [[ -z "${VSIX_PATH}" || ! -f "${VSIX_PATH}" ]]; then
  echo "[remote-vsix] VSIX not found (auto-detect failed). Build first via: npm --prefix extensions/vscode run package" >&2
  exit 2
fi

# Prefer using VS Code command to install into remote host if available.
# This works inside remote windows and will install to the remote extension host.
if command -v code >/dev/null 2>&1; then
  echo "[remote-vsix] Installing via 'code --install-extension' to current window target"
  if code --install-extension "${VSIX_PATH}" --force; then
    echo "[remote-vsix] Installed via code CLI"
    exit 0
  else
    echo "[remote-vsix] WARN: code CLI invocation failed; falling back to manual copy"
  fi
fi

# Fallback: write VSIX into workspace .mcp/ide and ask VS Code to install it via command (when possible)
IDE_DIR="${WS_ROOT}/.mcp/ide"
mkdir -p "${IDE_DIR}"
TARGET_VSIX="${IDE_DIR}/$(basename "${VSIX_PATH}")"
cp -f "${VSIX_PATH}" "${TARGET_VSIX}"
echo "[remote-vsix] Copied VSIX to ${TARGET_VSIX}. If VS Code is open remotely, run:"
echo "[remote-vsix]  - Workbench: Install Extension (select ${TARGET_VSIX})"
exit 0






