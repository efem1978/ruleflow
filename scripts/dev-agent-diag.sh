#!/usr/bin/env bash
set -euo pipefail

echo "[diag] docker compose ps (short)"
docker compose ps || true

echo "[diag] try locate container id by label"
CID=$(docker ps -qa --filter "label=com.docker.compose.service=dev-agent" | head -n1 || true)
if [ -z "${CID:-}" ]; then
  CID=$(docker compose ps -q dev-agent || true)
fi
echo "[diag] dev-agent CID=${CID:-<none>}"
if [ -n "${CID:-}" ]; then
  echo "[diag] inspect health/status"
  docker inspect -f '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$CID" || true
  echo "[diag] last 100 logs (2m)"
  docker logs --since 2m --tail 100 "$CID" || true
else
  echo "[diag] dev-agent container not found"
fi

echo "[diag] host dashboard snapshot"
if [ -f .mcp/dashboard/status.json ]; then
  python3 - <<'PY'
from pathlib import Path
import json
p=Path('.mcp/dashboard/status.json')
d=json.loads(p.read_text(encoding='utf-8'))
print('[diag] keys:', sorted(d.keys()))
cov=d.get('coverage') or {}
print('[diag] weak_count=', len(cov.get('weak') or []))
print('[diag] progress=', (d.get('progress') or {}).get('overall'))
PY
else
  echo "[diag] .mcp/dashboard/status.json not found"
fi

echo "[diag] done"

