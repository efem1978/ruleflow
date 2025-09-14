#!/usr/bin/env bash
set -euo pipefail

# One-click installer for MCP tool + VS Code extension (best effort for JetBrains)
# - Creates .mcp/venv and installs Python package (editable)
# - Initializes assistant config and ingests rules
# - Runs tests to produce coverage.xml
# - Builds VS Code VSIX and installs via `code` CLI (if available)
# - Builds JetBrains plugin zip (if gradle/docker available) best-effort

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[install] create venv"
python3 -m venv .mcp/venv
echo "[install] upgrade pip"
.mcp/venv/bin/python -m pip -q install -U pip >/dev/null 2>&1 || true
echo "[install] toolchain"
.mcp/venv/bin/python -m pip -q install ruff black isort mypy bandit pytest pytest-cov pre-commit types-PyYAML cryptography >/dev/null 2>&1 || true
echo "[install] project (editable)"
.mcp/venv/bin/python -m pip -q install -e . >/dev/null 2>&1

echo "[install] init + ingest rules"
.mcp/venv/bin/python -m mcp_rules_assistant.cli init >/dev/null 2>&1 || true
.mcp/venv/bin/python -m mcp_rules_assistant.cli ingest-rules README.md docs/ >/dev/null 2>&1 || true

echo "[install] tests + coverage"
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .mcp/venv/bin/python -m pytest -q -p pytest_cov --cov=mcp_rules_assistant --cov-report=xml:coverage.xml || true
.mcp/venv/bin/python -m mcp_rules_assistant.cli status-update --json >/dev/null 2>&1 || true

echo "[install] VS Code extension build + install"
if command -v npm >/dev/null 2>&1 && command -v code >/dev/null 2>&1; then
  npm --prefix extensions/vscode run compile >/dev/null 2>&1 || true
  npm --prefix extensions/vscode run package >/dev/null 2>&1 || true
  VSIX="extensions/vscode/mcp-rules-assistant-0.2.5.vsix"
  if [ -f "$VSIX" ]; then
    code --install-extension "$VSIX" --force >/dev/null 2>&1 || true
    echo "[install] VS Code extension installed: $VSIX"
  else
    echo "[install] VSIX not found; skipped"
  fi
else
  echo "[install] VS Code or npm not available; skipped"
fi

echo "[install] JetBrains plugin (best-effort)"
if command -v docker >/dev/null 2>&1; then
  docker compose run --rm jb-package >/dev/null 2>&1 || true
  if [ -f extensions/jetbrains/build/distributions/*.zip ]; then
    echo "[install] JetBrains plugin zip ready under extensions/jetbrains/build/distributions"
  fi
else
  echo "[install] docker not available; skipped JetBrains packaging"
fi

echo "[install] validating..."
OK_CLI=0
if .mcp/venv/bin/python -m mcp_rules_assistant.cli version >/dev/null 2>&1; then OK_CLI=1; fi
OK_STATUS=0
if [ -f .mcp/dashboard/status.json ]; then OK_STATUS=1; fi
OK_VSIX=0
if command -v code >/dev/null 2>&1; then
  if code --list-extensions | grep -qi 'ruleflow.mcp-rules-assistant'; then OK_VSIX=1; fi
fi
echo "- CLI: $OK_CLI"
echo "- Status: $OK_STATUS"
echo "- VSIX installed: $OK_VSIX"

echo "[install] done"
echo "- MCP venv: .mcp/venv"
echo "- Status: .mcp/dashboard/status.json (if tests passed)"
echo "- VS Code command palette: 'RuleFlow: Open Panel' | 'RuleFlow: Load Coverage' | 'RuleFlow: Natural Command'"
