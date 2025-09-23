#!/usr/bin/env bash
set -euo pipefail

echo "[post-create] Starting Dev Container setup"

# Ensure we're at repo root (Dev Containers runs here by default)
ROOT_DIR="$(pwd)"
echo "[post-create] Workspace root: $ROOT_DIR"

# 1) Ensure Node.js (optional, if building frontend)
if ! command -v node >/dev/null 2>&1; then
  echo "[post-create] Installing Node.js 20 (no features build)"
  if command -v apt-get >/dev/null 2>&1; then
    set -x
    apt-get update -y
    # Prefer NodeSource for v20 if available; fallback to distro nodejs
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - || true
    apt-get install -y nodejs || apt-get install -y nodejs npm || true
    set +x
  else
    echo "[post-create] Skipping Node install (no apt). You can install manually."
  fi
fi

# 2) Python venv under workspace to avoid global permission issues
if ! command -v python3 >/dev/null 2>&1; then
  echo "[post-create] ERROR: python3 not found in container" >&2
  exit 1
fi

mkdir -p .mcp/venv || true
python3 -m venv .mcp/venv
.mcp/venv/bin/python -m pip install -U pip setuptools wheel

# Install project (editable) if it's a Python package
if [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
  echo "[post-create] Installing workspace package (editable)"
  .mcp/venv/bin/pip install -e .
fi

# Common dev tools
.mcp/venv/bin/pip install -U ruff black isort mypy bandit pytest pytest-cov pre-commit

# Optional: install git hooks if pre-commit config exists
if [ -f ".pre-commit-config.yaml" ]; then
  .mcp/venv/bin/pre-commit install || true
fi

# 3) VS Code extension dependencies (front-end)
if [ -d "extensions/vscode" ]; then
  echo "[post-create] Installing VS Code extension deps"
  (cd extensions/vscode && npm install && npm run compile) || true
fi

# 4) Drop a marker and basic dashboard directory
mkdir -p .mcp/dashboard || true
echo "ok $(date -Iseconds)" > .mcp/dashboard/post_create_done

# 5) Final echo for Dev Containers log
echo "[post-create] Completed successfully"
