#!/usr/bin/env bash
set -euo pipefail

# Demo: generate RSA key pair, issue an rs256 license, activate and verify.
# Requirements: openssl; Python "cryptography" package available to the CLI for rs256.

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${HERE}/../.mcp/keys"
mkdir -p "${WORK}"

PRIV="${WORK}/private.pem"
PUB="${WORK}/public.pem"
LIC="${WORK}/lic.json"

echo "[license-demo] Generating RSA key pair under ${WORK} ..."
openssl genrsa -out "${PRIV}" 2048 >/dev/null 2>&1
openssl rsa -in "${PRIV}" -pubout -out "${PUB}" >/dev/null 2>&1

echo "[license-demo] Exporting MCP_LICENSE_PUBKEY from ${PUB} ..."
export MCP_LICENSE_PUBKEY="$(cat "${PUB}")"

ISSUED_TO="Demo User"
EXPIRES="$(date -v+365d +%Y-%m-%d 2>/dev/null || date -d '+365 days' +%Y-%m-%d)"
MACHINE=""

echo "[license-demo] Generating rs256 license via CLI ..."
python3 -m mcp_rules_assistant.cli license-generate \
  --issued-to "${ISSUED_TO}" --expires "${EXPIRES}" --machine "${MACHINE}" \
  --alg rs256 --private-key "${PRIV}" --out "${LIC}"

echo "[license-demo] Activating license ..."
python3 -m mcp_rules_assistant.cli license-activate --file "${LIC}"

echo "[license-demo] Verifying license ..."
python3 -m mcp_rules_assistant.cli license-verify

echo "[license-demo] Done. Keys at ${WORK}." 

