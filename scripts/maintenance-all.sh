#!/usr/bin/env sh
set -e

echo "[maintenance] installing hooks and regenerating CI..."
python -m mcp_rules_assistant.cli maintenance || python3 -m mcp_rules_assistant.cli maintenance

echo "[maintenance] running preflight..."
sh scripts/preflight.sh

echo "[maintenance] local CI run (python tests + coverage gate)..."
make -s local-ci-run || true

echo "[maintenance] done."

