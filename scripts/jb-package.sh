#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."/extensions/jetbrains
if command -v ./gradlew >/dev/null 2>&1; then
  ./gradlew buildPlugin -i || { echo '[jb] buildPlugin failed (report-only)'; exit 1; }
else
  gradle buildPlugin -i || { echo '[jb] buildPlugin failed (report-only)'; exit 1; }
fi
echo "[jb] buildPlugin done. Artifacts in build/distributions"

