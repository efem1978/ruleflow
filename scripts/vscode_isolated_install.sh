#!/usr/bin/env bash
set -euo pipefail
# Install the packaged VSIX into isolated dirs for this workspace only.
# It also removes any globally installed copy of the same extension id.

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VSIX_PATH="${1:-${WS_ROOT}/extensions/vscode/mcp-rules-assistant-0.2.5.vsix}"
EXT_ID="ruleflow.mcp-rules-assistant"

VS_EXT_DIR="${WS_ROOT}/.mcp/vscode-extensions"
VS_USER_DIR="${WS_ROOT}/.mcp/vscode-user"
CUR_EXT_DIR="${WS_ROOT}/.mcp/cursor-extensions"
CUR_USER_DIR="${WS_ROOT}/.mcp/cursor-user"

mkdir -p "${VS_EXT_DIR}" "${VS_USER_DIR}" "${CUR_EXT_DIR}" "${CUR_USER_DIR}"

echo "[Isolated] VSIX: ${VSIX_PATH}"
if [[ ! -f "${VSIX_PATH}" ]]; then
  echo "ERROR: VSIX not found at ${VSIX_PATH}" >&2
  exit 1
fi

have_code=0; have_cursor=0
if command -v code >/dev/null 2>&1; then have_code=1; fi
if command -v cursor >/dev/null 2>&1; then have_cursor=1; fi

if [[ ${have_code} -eq 1 ]]; then
  echo "[VS Code] Uninstall any global ${EXT_ID}..."
  if code --list-extensions | grep -qi "^${EXT_ID}$"; then
    code --uninstall-extension "${EXT_ID}" || true
  fi
  echo "[VS Code] Install to isolated dirs..."
  code --install-extension "${VSIX_PATH}" \
       --extensions-dir "${VS_EXT_DIR}" \
       --user-data-dir "${VS_USER_DIR}"
  echo "[VS Code] Installed into: ${VS_EXT_DIR} (user-data: ${VS_USER_DIR})"
  echo "[VS Code] Launch with isolation: code . --extensions-dir '${VS_EXT_DIR}' --user-data-dir '${VS_USER_DIR}'"
else
  echo "[VS Code] 'code' CLI not found. Skipping VS Code install."
fi

if [[ ${have_cursor} -eq 1 ]]; then
  echo "[Cursor] Uninstall any global ${EXT_ID}..."
  if cursor --list-extensions | grep -qi "^${EXT_ID}$"; then
    cursor --uninstall-extension "${EXT_ID}" || true
  fi
  echo "[Cursor] Install to isolated dirs..."
  cursor --install-extension "${VSIX_PATH}" \
         --extensions-dir "${CUR_EXT_DIR}" \
         --user-data-dir "${CUR_USER_DIR}" || true
  echo "[Cursor] Installed into: ${CUR_EXT_DIR} (user-data: ${CUR_USER_DIR})"
  echo "[Cursor] Launch with isolation: cursor . --extensions-dir '${CUR_EXT_DIR}' --user-data-dir '${CUR_USER_DIR}'"
else
  echo "[Cursor] 'cursor' CLI not found. Skipping Cursor install."
fi

echo "[Done] Isolated installation script completed."

