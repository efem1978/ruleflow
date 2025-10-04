#!/usr/bin/env bash
set -euo pipefail

# Remove RuleFlow from Cursor only (no theme changes)

EXT_ID="ruleflow.mcp-rules-assistant"
HOME_DIR="${HOME:-$PWD}"

if command -v cursor >/dev/null 2>&1; then
  echo "[Cursor] Uninstalling extension ${EXT_ID} (if present)"
  cursor --uninstall-extension "${EXT_ID}" >/dev/null 2>&1 || true
else
  echo "[Cursor] CLI not found; skipping CLI uninstall"
fi

purge_dir() {
  local d="$1"; shift || true
  if [[ -d "$d" ]]; then
    echo "[Cursor] Scanning $d"
    shopt -s nullglob
    local matches=("${d}/${EXT_ID}-"*)
    for m in ${matches[@]:-}; do
      echo "[Cursor] Removing $m"
      rm -rf "$m" || true
    done
  fi
}

purge_dir "${HOME_DIR}/.cursor/extensions"
purge_dir "${HOME_DIR}/Library/Application Support/Cursor/extensions"

echo "Done. Cursor will remain untouched otherwise (no theme changes)."
