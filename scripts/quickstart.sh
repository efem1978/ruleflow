#!/usr/bin/env bash
set -euo pipefail

echo "[quickstart] init + ingest rules + generate ci + install hooks + status"
python3 -m mcp_rules_assistant.cli init || true
python3 -m mcp_rules_assistant.cli ingest-rules README.md docs/ || true
python3 -m mcp_rules_assistant.cli generate-ci || true
python3 -m mcp_rules_assistant.cli install-hooks || true
python3 -m mcp_rules_assistant.cli status-update || true
echo "[quickstart] done"

