#!/usr/bin/env bash
set -euo pipefail

# Run backend doctor and diagnose INSIDE dev container

if [[ ! -x ".mcp/venv/bin/python" ]]; then
  echo "[doctor] creating venv"
  python3 -m venv .mcp/venv
fi

.mcp/venv/bin/python -m pip install -U pip setuptools wheel >/dev/null 2>&1 || true
.mcp/venv/bin/python -m pip install -e . >/dev/null 2>&1 || true

echo "[doctor] running CLI doctor"
.mcp/venv/bin/python -m mcp_rules_assistant.cli doctor --fix --clear-fake | tee .mcp/dashboard/doctor_container.json

echo "[doctor] running diagnose"
.mcp/venv/bin/python -m mcp_rules_assistant.cli diagnose | tee .mcp/dashboard/diagnose_container.json

echo "[doctor] done"

