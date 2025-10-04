#!/usr/bin/env bash
set -euo pipefail

# Run VS Code extension tests headlessly inside Linux (Node 20 + xvfb).
# Requires Docker on host. Mounts repo at /work and runs inside extensions/vscode.

IMAGE="node:20-bookworm"
WORKDIR="/work/extensions/vscode"

echo "[vscode-docker] pulling base image: ${IMAGE}"
docker pull "${IMAGE}" >/dev/null

echo "[vscode-docker] starting test container..."
docker run --rm -t \
  -v "${PWD}":/work \
  -w "${WORKDIR}" \
  -e CI=1 -e NO_COLOR=1 -e FORCE_COLOR=0 \
  -e DEBUG \
  -e MCP_VSCODE_TEST_ARGS \
  "${IMAGE}" bash -lc "\
    set -e; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update -y >/dev/null; \
    apt-get install -y --no-install-recommends \
      xvfb xauth \
      libglib2.0-0 libgdk-pixbuf-2.0-0 \
      libgtk-3-0 libasound2 libnss3 libxss1 libxshmfence1 \
      libgbm1 libdrm2 libxdamage1 libxfixes3 libxcomposite1 \
      libxi6 libxrandr2 libatk-bridge2.0-0 libx11-xcb1 libxext6 \
      libxkbfile1 libxkbcommon0 libwayland-client0 libxrender1 \
      ca-certificates >/dev/null; \
    npm ci >/dev/null; \
    xvfb-run -a -s '-screen 0 1024x768x24' npm test \
  "

echo "[vscode-docker] done."
