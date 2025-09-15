#!/usr/bin/env bash
set -euo pipefail

echo "[ci-security] SBOM generation"
python3 scripts/sbom_generate.py || true

echo "[ci-security] Bandit (if available)"
if command -v bandit >/dev/null 2>&1; then
  bandit -q -r mcp_rules_assistant || true
else
  echo "bandit not found; skip"
fi

echo "[ci-security] Semgrep (if available)"
if command -v semgrep >/dev/null 2>&1; then
  semgrep ci || semgrep --config p/ci || true
else
  echo "semgrep not found; skip"
fi

echo "[ci-security] Hadolint (if available)"
if command -v hadolint >/dev/null 2>&1; then
  hadolint Dockerfile || true
else
  echo "hadolint not found; skip"
fi

echo "[ci-security] Done"

