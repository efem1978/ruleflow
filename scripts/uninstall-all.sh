#!/usr/bin/env bash
set -euo pipefail

echo "[uninstall] removing venv and build artifacts"
rm -rf .mcp/venv || true
rm -f coverage.xml cov*.json pytest-junit.xml || true

if command -v code >/dev/null 2>&1; then
  echo "[uninstall] uninstalling VS Code extension ruleflow.mcp-rules-assistant (best-effort)"
  code --uninstall-extension ruleflow.mcp-rules-assistant --force >/dev/null 2>&1 || true
fi

echo "[uninstall] done"

