#!/usr/bin/env bash
set -euo pipefail

EXT_ID="ruleflow.mcp-rules-assistant"
echo "[Purge] Target extension id: ${EXT_ID}"

# 1) Uninstall via VS Code CLI when available and not pointing to Cursor
CODE_BIN="${VSCODE_BIN:-code}"
if command -v "${CODE_BIN}" >/dev/null 2>&1; then
  real_path="$(command -v "${CODE_BIN}")"
  target_path="$(readlink "${real_path}" 2>/dev/null || echo "")"
  probe="${real_path} ${target_path}"
  if echo "${probe}" | grep -qi "Cursor.app"; then
    echo "[VS Code] '${CODE_BIN}' appears to point to Cursor.app — skipping VS Code uninstall to avoid popups."
  else
    if "${CODE_BIN}" --list-extensions | grep -qi "^${EXT_ID}$"; then
      echo "[VS Code] Uninstalling ${EXT_ID} via ${CODE_BIN}..."
      "${CODE_BIN}" --uninstall-extension "${EXT_ID}" || true
    else
      echo "[VS Code] No global ${EXT_ID} listed."
    fi
  fi
else
  echo "[VS Code] CLI not found; skipping VS Code uninstall."
fi

if [[ "${RULEFLOW_SKIP_CURSOR:-}" != "1" ]] && command -v cursor >/dev/null 2>&1; then
  if cursor --list-extensions | grep -qi "^${EXT_ID}$"; then
    echo "[Cursor] Uninstalling ${EXT_ID} via cursor CLI..."
    cursor --uninstall-extension "${EXT_ID}" || true
  else
    echo "[Cursor] No global ${EXT_ID} listed."
  fi
else
  echo "[Cursor] Skipped (RULEFLOW_SKIP_CURSOR=1) or CLI not found; skipping Cursor uninstall."
fi

# 2) Remove residual extension folders (best-effort, common locations)
removed_any=0
purge_dir() {
  local d="$1"; shift || true
  if [[ -d "$d" ]]; then
    echo "[Purge] Scanning $d"
    shopt -s nullglob
    local matches=()
    matches=("${d}/${EXT_ID}-"*)
    if (( ${#matches[@]} > 0 )); then
      for m in "${matches[@]}"; do
        echo "[Purge] Removing $m"
        rm -rf "$m" || true
        removed_any=1
      done
    fi
  fi
}

OS="$(uname -s 2>/dev/null || echo unknown)"
HOME_DIR="${HOME:-$PWD}"
purge_dir "${HOME_DIR}/.vscode/extensions"
if [[ "${RULEFLOW_SKIP_CURSOR:-}" != "1" ]]; then
  purge_dir "${HOME_DIR}/.cursor/extensions"
fi
if [[ "$OS" == "Darwin" ]]; then
  purge_dir "${HOME_DIR}/Library/Application Support/Code/extensions"
  if [[ "${RULEFLOW_SKIP_CURSOR:-}" != "1" ]]; then
    purge_dir "${HOME_DIR}/Library/Application Support/Cursor/extensions"
  fi
elif [[ "$OS" == "Linux" ]]; then
  purge_dir "${HOME_DIR}/.config/Code/extensions"
  if [[ "${RULEFLOW_SKIP_CURSOR:-}" != "1" ]]; then
    purge_dir "${HOME_DIR}/.config/Cursor/extensions"
  fi
fi

if [[ $removed_any -eq 0 ]]; then
  echo "[Purge] No residual extension directories found."
fi

echo "[Purge] Done. Please fully quit VS Code & Cursor (Cmd+Q) and relaunch."
