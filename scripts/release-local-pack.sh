#!/usr/bin/env bash
set -euo pipefail

# One-click local release bundle (no push)
# - Build Python package (wheel/sdist)
# - Build VS Code VSIX
# - Generate release notes snippet (best-effort)
# - Bundle artifacts under dist/release-bundle-<ver>.tar.gz

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

VER=$(python3 - <<'PY'
import re,sys
txt=open('pyproject.toml','r',encoding='utf-8').read()
m=re.search(r"^version\s*=\s*\"([^\"]+)\"", txt, flags=re.M)
print(m.group(1) if m else '0.0.0')
PY
)

echo "[release] Building Python package..."
python3 -m pip install --upgrade build twine >/dev/null 2>&1 || true
python3 -m build

echo "[release] Building VS Code VSIX..."
npm --prefix extensions/vscode run compile >/dev/null 2>&1 || true
if command -v vsce >/dev/null 2>&1; then
  (cd extensions/vscode && vsce package --no-dependencies)
else
  npx --yes @vscode/vsce package --no-dependencies -o extensions/vscode/*.vsix || true
fi

echo "[release] Generating release notes snippet (best-effort)..."
python3 scripts/release-note-from-report.py --report .mcp/dashboard/release_check.md --out .mcp/dashboard/release_note_snippet.md || true

OUTDIR="dist/release-artifacts"
mkdir -p "$OUTDIR"
echo "[release] Collecting artifacts into $OUTDIR"
cp -f dist/*.{whl,tar.gz} "$OUTDIR" 2>/dev/null || true
cp -f extensions/vscode/*.vsix "$OUTDIR" 2>/dev/null || true
cp -f coverage.xml pytest-junit.xml near.* "$OUTDIR" 2>/dev/null || true
cp -f .mcp/dashboard/release_check.md "$OUTDIR" 2>/dev/null || true
cp -f .mcp/dashboard/release_note_snippet.md "$OUTDIR" 2>/dev/null || true

TARBALL="dist/release-bundle-${VER}.tar.gz"
echo "[release] Creating bundle $TARBALL"
tar czf "$TARBALL" -C "$OUTDIR" . || true
echo "[release] Done. Bundle: $TARBALL"

