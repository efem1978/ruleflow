#!/usr/bin/env sh
set -e

echo "[preflight] scanning for banned patterns in docs..."
if rg -n "docker-compose.yml|--serve|localhost:9000|index.html|status.js" DEVELOPMENT.md docs README.md >/dev/null 2>&1; then
  echo "[preflight] banned pattern detected in docs; please fix" >&2
  rg -n "docker-compose.yml|--serve|localhost:9000|index.html|status.js" DEVELOPMENT.md docs README.md || true
  exit 1
fi

echo "[preflight] validating compose.yml..."
if command -v docker >/dev/null 2>&1; then
  docker compose config -q || { echo "[preflight] compose validation failed" >&2; exit 1; }
else
  echo "[preflight] docker not found; skip compose validation"
fi

echo "[preflight] running docs anchors tests..."
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/docs/test_docs_anchors.py

echo "[preflight] OK"
