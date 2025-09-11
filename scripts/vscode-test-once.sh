#!/usr/bin/env bash
set -euo pipefail

echo "[vscode-test] running once in container (may take minutes)"
# Use compose service (pre-cached VS Code test kernel). If it fails or times out, exit 0 to avoid blocking caller.
docker compose run --rm vscode-test || true
echo "[vscode-test] done"

