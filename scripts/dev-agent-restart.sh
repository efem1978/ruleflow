#!/usr/bin/env bash
set -euo pipefail

echo "[dev-agent] restart"
docker compose rm -sf dev-agent >/dev/null 2>&1 || true
docker compose up -d dev-agent
docker compose ps dev-agent || true
echo "[dev-agent] last 80 lines (if available)"
docker compose logs --no-color --tail=80 dev-agent || true
echo "[dev-agent] status.json (host)"
if [ -f .mcp/dashboard/status.json ]; then
  tail -n +1 .mcp/dashboard/status.json | sed -n '1,80p'
else
  echo "(not found)"
fi
echo "[dev-agent] done"

