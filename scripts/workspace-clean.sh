#!/usr/bin/env bash
set -euo pipefail

echo "[workspace-clean] removing local artifacts..."
rm -f coverage.xml cov.json cov_cli.json pytest-junit.xml || true
rm -f near.txt near.csv near.json || true
rm -rf htmlcov || true
rm -f bad.py ok2.py ok.txt docs/b.txt || true
rm -f extensions/vscode/*.vsix || true
echo "[workspace-clean] done"

