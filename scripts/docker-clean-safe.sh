#!/usr/bin/env bash
set -euo pipefail

# Safe Docker cleanup for this project (dry-run by default)
# Usage:
#   scripts/docker-clean-safe.sh            # list only (dry-run)
#   scripts/docker-clean-safe.sh --yes      # actually remove
#   scripts/docker-clean-safe.sh --filters 'name=contextual|mcp|ruleflow'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILTERS=${1:-}
DO_REMOVE=false
for a in "$@"; do
  if [[ "$a" == "--yes" ]]; then DO_REMOVE=true; fi
  if [[ "$a" == "--filters"* ]]; then FILTERS="${a#--filters }"; fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "[clean] docker not found; nothing to do" >&2
  exit 0
fi

# default filters: try to match this repo name keywords
if [[ -z "${FILTERS}" ]]; then
  FILTERS='name=contextual|cohesion|programming|mcp|ruleflow'
fi

echo "[clean] Using filters: ${FILTERS}"

echo "[clean] Listing containers (all) matching filters"
docker ps -a --format '{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}' | egrep -i "${FILTERS}" || true

echo "[clean] Listing images matching filters"
docker images --format '{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}' | egrep -i "${FILTERS}" || true

echo "[clean] Listing volumes matching filters"
docker volume ls --format '{{.Name}}' | egrep -i "${FILTERS}" || true

if [[ "${DO_REMOVE}" != "true" ]]; then
  echo "[clean] DRY-RUN. Append --yes to actually remove matched resources."
  exit 0
fi

# stop and remove containers
CIDS=$(docker ps -a --format '{{.ID}}\t{{.Names}}' | egrep -i "${FILTERS}" | awk '{print $1}' || true)
if [[ -n "${CIDS}" ]]; then
  echo "[clean] Removing containers: ${CIDS}" && docker rm -f ${CIDS}
else
  echo "[clean] No containers to remove"
fi

# remove images (best-effort)
IIDS=$(docker images --format '{{.ID}}\t{{.Repository}}:{{.Tag}}' | egrep -i "${FILTERS}" | awk '{print $1}' | sort -u || true)
if [[ -n "${IIDS}" ]]; then
  echo "[clean] Removing images: ${IIDS}" && docker rmi -f ${IIDS} || true
else
  echo "[clean] No images to remove"
fi

# remove volumes (best-effort)
VOLS=$(docker volume ls --format '{{.Name}}' | egrep -i "${FILTERS}" | tr '\n' ' ' || true)
if [[ -n "${VOLS}" ]]; then
  echo "[clean] Removing volumes: ${VOLS}" && xargs -r docker volume rm <<<"${VOLS}" || true
else
  echo "[clean] No volumes to remove"
fi

echo "[clean] Done"
