#!/usr/bin/env bash
set -euo pipefail

LOG_DIR=".mcp/dashboard"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy.log"

echo "[deploy] start $(date -Is)" | tee -a "$LOG_FILE"

# 1) Resolve VS Code CLI (refuse Cursor.app)
VSCODE_BIN="${VSCODE_BIN:-}"
if [[ -z "${VSCODE_BIN}" ]]; then
  if [[ -x "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" ]]; then
    VSCODE_BIN="/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
  elif command -v code >/dev/null 2>&1; then
    CANDIDATE="$(command -v code)"; TGT="$(readlink "$CANDIDATE" 2>/dev/null || true)"
    PROBE="$CANDIDATE $TGT"
    if echo "$PROBE" | grep -qi 'Cursor.app'; then
      echo "[deploy] ERROR: 'code' CLI points to Cursor.app. Please set VSCODE_BIN to VS Code CLI path." | tee -a "$LOG_FILE"
      echo "[deploy] Example: export VSCODE_BIN='/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code'" | tee -a "$LOG_FILE"
      exit 2
    fi
    VSCODE_BIN="$CANDIDATE"
  else
    echo "[deploy] ERROR: VS Code CLI not found. Install VS Code and enable 'code' in PATH, or set VSCODE_BIN." | tee -a "$LOG_FILE"
    exit 2
  fi
fi
echo "[deploy] VSCODE_BIN=$VSCODE_BIN" | tee -a "$LOG_FILE"

# 2) Ensure venv and install package
if [[ ! -x ".mcp/venv/bin/python" ]]; then
  python3 -m venv .mcp/venv | tee -a "$LOG_FILE"
fi
.mcp/venv/bin/python -m pip install -U pip setuptools wheel >/dev/null 2>&1 || true
.mcp/venv/bin/python -m pip install -e . >/dev/null 2>&1
echo "[deploy] python package installed (editable)" | tee -a "$LOG_FILE"

# 3) Find VSIX (build if missing best-effort)
VSIX_PATH="$(ls -1 extensions/vscode/mcp-rules-assistant-*.vsix 2>/dev/null | head -n1 || true)"
if [[ -z "$VSIX_PATH" ]]; then
  echo "[deploy] VSIX missing; building (best-effort)" | tee -a "$LOG_FILE"
  if command -v npm >/dev/null 2>&1; then
    npm --prefix extensions/vscode run -s package | tee -a "$LOG_FILE" || true
    VSIX_PATH="$(ls -1 extensions/vscode/mcp-rules-assistant-*.vsix 2>/dev/null | head -n1 || true)"
  fi
fi
if [[ -z "$VSIX_PATH" ]]; then
  echo "[deploy] ERROR: cannot find or build VSIX." | tee -a "$LOG_FILE"
  exit 3
fi
echo "[deploy] VSIX=$VSIX_PATH" | tee -a "$LOG_FILE"

# 4) Install VSIX into isolated dirs
mkdir -p .mcp/vscode-extensions .mcp/vscode-user
"$VSCODE_BIN" --install-extension "$VSIX_PATH" \
  --extensions-dir ".mcp/vscode-extensions" \
  --user-data-dir ".mcp/vscode-user" 2>&1 | tee -a "$LOG_FILE"

# 5) Launch VS Code isolated and open panel
"$VSCODE_BIN" . \
  --extensions-dir ".mcp/vscode-extensions" \
  --user-data-dir ".mcp/vscode-user" \
  --new-window \
  --command "mcpRulesAssistant.openPanel" 2>&1 | tee -a "$LOG_FILE" &

echo "[deploy] done $(date -Is)" | tee -a "$LOG_FILE"

