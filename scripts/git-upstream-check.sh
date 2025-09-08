#!/usr/bin/env bash
set -euo pipefail

current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
if [ -z "$current_branch" ] || [ "$current_branch" = "HEAD" ]; then
  echo "[git-upstream] not on a named branch (detached HEAD?)"
  exit 0
fi

upstream_ref="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
if [ -z "$upstream_ref" ]; then
  echo "[git-upstream] branch '$current_branch' has no upstream set. Suggested fix:"
  echo "  git branch --set-upstream-to origin/main $current_branch  # or set to desired remote/branch"
  exit 0
fi

remote_name="${upstream_ref%%/*}"
remote_branch="${upstream_ref#*/}"

if ! git fetch --dry-run "$remote_name" &>/dev/null; then
  echo "[git-upstream] remote '$remote_name' not reachable; check network/credentials."
  exit 0
fi

exists=$(git ls-remote --heads "$remote_name" "$remote_branch" | wc -l | tr -d ' \n')
if [ "$exists" = "0" ]; then
  echo "[git-upstream] upstream '$upstream_ref' appears to be gone. Suggested fixes:"
  echo "  # Option A: re-point upstream to origin/main"
  echo "  git branch --set-upstream-to origin/main $current_branch"
  echo "  # Option B: create the remote branch"
  echo "  git push -u $remote_name $current_branch  # if allowed"
else
  echo "[git-upstream] upstream '$upstream_ref' is present."
fi

