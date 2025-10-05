#!/usr/bin/env bash
set -euo pipefail

# Forbid committing common binary artifacts and installer packages
# Allowed images (png/jpg/svg) are not blocked here; size gate handles large files
PATTERN='\.(vsix|zip|tar|tgz|gz|jar|exe|dll|dmg|iso|class|o|so|7z|rar|bin|img|msi)$'

# List staged added/modified files
FILES=$(git diff --cached --name-only --diff-filter=AM || true)
if [[ -z "${FILES}" ]]; then
  exit 0
fi

BAD=$(echo "${FILES}" | grep -E "${PATTERN}" || true)
if [[ -n "${BAD}" ]]; then
  echo "[forbid-binaries] Error: forbidden binary artifacts staged:" >&2
  echo "${BAD}" >&2
  echo "Hint: add these to .gitignore or generate them in CI only." >&2
  exit 1
fi

exit 0
