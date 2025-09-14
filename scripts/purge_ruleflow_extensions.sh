#!/usr/bin/env bash
set -euo pipefail

EXT_ID="ruleflow.mcp-rules-assistant"
echo "[Purge] Target extension id: ${EXT_ID}"

# 1) Uninstall via CLIs when available
if command -v code >/dev/null 2>&1; then
  if code --list-extensions | grep -qi "^${EXT_ID}$"; then
    echo "[VS Code] Uninstalling ${EXT_ID} via code CLI..."
    code --uninstall-extension "${EXT_ID}" || true
  else
    echo "[VS Code] No global ${EXT_ID} listed."
  fi
else
  echo "[VS Code] 'code' CLI not found; skipping CLI uninstall."
fi

if command -v cursor >/dev/null 2>&1; then
  if cursor --list-extensions | grep -qi "^${EXT_ID}$"; then
    echo "[Cursor] Uninstalling ${EXT_ID} via cursor CLI..."
    cursor --uninstall-extension "${EXT_ID}" || true
  else
    echo "[Cursor] No global ${EXT_ID} listed."
  fi
else
  echo "[Cursor] 'cursor' CLI not found; skipping CLI uninstall."
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
purge_dir "${HOME_DIR}/.cursor/extensions"
if [[ "$OS" == "Darwin" ]]; then
  purge_dir "${HOME_DIR}/Library/Application Support/Code/extensions"
  purge_dir "${HOME_DIR}/Library/Application Support/Cursor/extensions"
elif [[ "$OS" == "Linux" ]]; then
  purge_dir "${HOME_DIR}/.config/Code/extensions"
  purge_dir "${HOME_DIR}/.config/Cursor/extensions"
fi

if [[ $removed_any -eq 0 ]]; then
  echo "[Purge] No residual extension directories found."
fi

echo "[Purge] Done. Please fully quit VS Code & Cursor (Cmd+Q) and relaunch."
