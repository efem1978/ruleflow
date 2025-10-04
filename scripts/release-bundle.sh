#!/usr/bin/env bash
set -euo pipefail

OUT_DIR=".mcp/dashboard"
mkdir -p "$OUT_DIR"
python3 scripts/sbom_generate.py || true
bash scripts/ci-security.sh || true

# Checksums
if ls dist/* >/dev/null 2>&1; then
  (cd dist && sha256sum * > ../.mcp/dashboard/dist.sha256 2>/dev/null || shasum -a 256 * > ../.mcp/dashboard/dist.sha256 || true)
fi
if ls extensions/vscode/*.vsix >/dev/null 2>&1; then
  (cd extensions/vscode && sha256sum *.vsix > ../../.mcp/dashboard/vsix.sha256 2>/dev/null || shasum -a 256 *.vsix > ../../.mcp/dashboard/vsix.sha256 || true)
fi

tar czf "$OUT_DIR/release_bundle.tgz" \
  -C "$OUT_DIR" \
  sbom.json \
  security_audit.jsonl \
  dist.sha256 \
  vsix.sha256 \
  coverage_summary.json \
  weak_top.csv \
  near_top.csv \
  groups.csv \
  2>/dev/null || true

echo "[release-bundle] Bundle at $OUT_DIR/release_bundle.tgz (best-effort)"

