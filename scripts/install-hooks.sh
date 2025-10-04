#!/usr/bin/env sh
set -e

# Prefer Python CLI if available
if command -v python >/dev/null 2>&1; then
  python -m mcp_rules_assistant.cli install-hooks && exit 0
fi
if command -v python3 >/dev/null 2>&1; then
  python3 -m mcp_rules_assistant.cli install-hooks && exit 0
fi

echo "[mcp] Python not found; installing minimal hooks (fallback)" >&2

mkdir -p .git/hooks

# commit-msg hook: require [step:...] token
cat > .git/hooks/commit-msg <<'EOF'
#!/usr/bin/env sh
MSG_FILE="$1"
if [ ! -f "$MSG_FILE" ]; then exit 0; fi
if ! grep -E '\[step:[^]]+\]' "$MSG_FILE" >/dev/null 2>&1; then
  echo "[mcp] commit message must include [step:当前步骤] token" >&2
  exit 1
fi
exit 0
EOF
chmod +x .git/hooks/commit-msg

# pre-push hook: run minimal pytest with coverage
cat > .git/hooks/pre-push <<'EOF'
#!/usr/bin/env sh
echo "[mcp] running minimal pre-push checks (fallback) ..."
if command -v pytest >/dev/null 2>&1; then
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q --maxfail=1 --disable-warnings -W error --strict-markers --cov --cov-report=term-missing || exit 1
else
  echo "[mcp] pytest not found; skipping fallback pre-push checks" >&2
fi
exit 0
EOF
chmod +x .git/hooks/pre-push

echo "[mcp] fallback hooks installed (.git/hooks/commit-msg, pre-push)"
