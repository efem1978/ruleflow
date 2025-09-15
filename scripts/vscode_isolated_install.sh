#!/usr/bin/env bash
set -euo pipefail
# Install the packaged VSIX into isolated dirs for this workspace only.
# Default: VS Code only. Cursor is skipped unless explicitly enabled.

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VSIX_PATH="${1:-${WS_ROOT}/extensions/vscode/mcp-rules-assistant-0.2.5.vsix}"
# Optional flag: pass "--include-cursor" as the second arg to also manage Cursor
INCLUDE_CURSOR="${2:-}"

# Prefer explicit VS Code CLI if provided, otherwise fall back to 'code'.
# If the resolved binary points to Cursor.app, refuse to use it to avoid Cursor popups.
CODE_BIN="${VSCODE_BIN:-code}"
have_code=0
if command -v "${CODE_BIN}" >/dev/null 2>&1; then
  real_path="$(command -v "${CODE_BIN}")"
  target_path="$(readlink "${real_path}" 2>/dev/null || echo "")"
  probe="${real_path} ${target_path}"
  if echo "${probe}" | grep -qi "Cursor.app"; then
    echo "[VS Code] WARNING: '${CODE_BIN}' appears to point to Cursor.app."
    echo "          To avoid Cursor launching, set VSCODE_BIN to VS Code CLI, e.g.:"
    echo "          export VSCODE_BIN='/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'"
    have_code=0
  else
    have_code=1
  fi
fi
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

have_cursor=0
if [[ "${INCLUDE_CURSOR}" == "--include-cursor" ]] && command -v cursor >/dev/null 2>&1; then have_cursor=1; fi

if [[ ${have_code} -eq 1 ]]; then
  echo "[VS Code] Uninstall any global ${EXT_ID}..."
  if "${CODE_BIN}" --list-extensions | grep -qi "^${EXT_ID}$"; then
    "${CODE_BIN}" --uninstall-extension "${EXT_ID}" || true
  fi
  echo "[VS Code] Install to isolated dirs..."
  "${CODE_BIN}" --install-extension "${VSIX_PATH}" \
       --extensions-dir "${VS_EXT_DIR}" \
       --user-data-dir "${VS_USER_DIR}"
  echo "[VS Code] Installed into: ${VS_EXT_DIR} (user-data: ${VS_USER_DIR})"
  echo "[VS Code] Launch with isolation: '${CODE_BIN}' . --extensions-dir '${VS_EXT_DIR}' --user-data-dir '${VS_USER_DIR}'"
else
  echo "[VS Code] CLI not found or refused (may point to Cursor). Skipping VS Code install."
fi

if [[ ${have_cursor} -eq 1 ]]; then
  echo "[Cursor] '--include-cursor' enabled: managing Cursor extension"
  echo "[Cursor] Uninstall any global ${EXT_ID}..."
  if cursor --list-extensions | grep -qi "^${EXT_ID}$"; then
    cursor --uninstall-extension "${EXT_ID}" || true
  fi
  echo "[Cursor] Install to isolated dirs..."
  cursor --install-extension "${VSIX_PATH}" \
         --extensions-dir "${CUR_EXT_DIR}" \
         --user-data-dir "${CUR_USER_DIR}" || true
  echo "[Cursor] Installed into: ${CUR_EXT_DIR} (user-data: ${CUR_USER_DIR})"
  echo "[Cursor] Launch with isolation (manual if needed): cursor . --extensions-dir '${CUR_EXT_DIR}' --user-data-dir '${CUR_USER_DIR}'"
else
  echo "[Cursor] Skipped (default) — pass --include-cursor to manage Cursor"
fi

echo "[Done] Isolated installation script completed."
