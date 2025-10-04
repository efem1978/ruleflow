#!/usr/bin/env bash
set -euo pipefail

# Remove remote VS Code extension copies (to be run INSIDE the dev container/remote)
# Typical locations under Linux container:
#   ~/.vscode-server/extensions/
#   ~/.vscode-server-insiders/extensions/

EXT_ID="ruleflow.mcp-rules-assistant"

purge_dir() {
  local dir="$1"
  if [[ -d "$dir" ]]; then
    echo "[remote-purge] scanning: $dir"
    shopt -s nullglob
    for p in "$dir/${EXT_ID}-"*; do
      echo "[remote-purge] removing: $p"
      rm -rf "$p" || true
    done
  fi
}

purge_dir "$HOME/.vscode-server/extensions"
purge_dir "$HOME/.vscode-server-insiders/extensions"

echo "[remote-purge] done. Restart VS Code window and reinstall extension."

