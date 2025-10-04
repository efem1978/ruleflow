#!/usr/bin/env bash
set -euo pipefail

# Container Backend Doctor (safe cleanup)
# - Purges remote VS Code extension cache for ruleflow.mcp-rules-assistant
# - Purges project .mcp caches that are safe to regenerate
# - Purges devcontainer workspace temp dirs under /workspaces for this project
# - Does NOT remove Docker images or containers

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

log(){ echo "[doctor] $*"; }

target_ext_id="ruleflow.mcp-rules-assistant"

# 1) Purge remote VS Code extension cache (server side)
purge_remote_exts(){
  local base1="$HOME/.vscode-server/extensions"; local base2="$HOME/.vscode-server-insiders/extensions"
  local cnt=0
  for base in "$base1" "$base2"; do
    if [[ -d "$base" ]]; then
      shopt -s nullglob
      for p in "$base/${target_ext_id}-"*; do
        log "remove: $p"; rm -rf "$p" || true; cnt=$((cnt+1))
      done
    fi
  done
  log "remote extensions removed: $cnt"
}

# 2) Purge project caches (safe to regenerate)
purge_project_caches(){
  local removed=0
  for p in \
    ".mcp/dashboard" \
    ".mcp/benchmark-report.json" \
    ".mcp/bandit-report.json" \
    "pytest-junit.xml" \
    "coverage.xml" \
    "extensions/vscode/out" \
    "extensions/vscode/coverage"
  do
    if [[ -e "$p" ]]; then
      log "rm -rf $p"; rm -rf "$p" || true; removed=$((removed+1))
    fi
  done
  log "project caches removed: $removed"
}

# 3) Ensure latest VSIX placed for install
stage_vsix(){
  mkdir -p .mcp/ide || true
  local vsix
  vsix=$(ls -1 extensions/vscode/mcp-rules-assistant-*.vsix 2>/dev/null | sort -V | tail -n1 || true)
  if [[ -n "${vsix}" && -f "${vsix}" ]]; then
    cp -f "$vsix" .mcp/ide/
    log "staged VSIX: .mcp/ide/$(basename "$vsix")"
  else
    log "no VSIX found; run: (cd extensions/vscode && npm run package)"
  fi
}

purge_remote_exts
purge_project_caches
stage_vsix

log "done. Next: In VS Code window → Extensions: Install from VSIX… → select .mcp/ide/mcp-rules-assistant-*.vsix"

