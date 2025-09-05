#!/usr/bin/env sh
# Usage: scripts/check-lcov.sh extensions/vscode/coverage/lcov.info 30
# Warn (non-blocking) if lcov line coverage percent is below threshold.

set -e
LCOV_FILE="$1"
THRESHOLD="${2:-30}"

if [ ! -f "$LCOV_FILE" ]; then
  echo "[lcov] file not found: $LCOV_FILE"
  exit 0
fi

# Sum all LF (lines found) and LH (lines hit)
LF_TOTAL=$(rg -n "^LF:" -r "$1" -N 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
LH_TOTAL=$(rg -n "^LH:" -r "$1" -N 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')

if [ -z "$LF_TOTAL" ] || [ "$LF_TOTAL" -eq 0 ]; then
  echo "[lcov] no lines found in $LCOV_FILE"
  exit 0
fi

PCT=$(awk "BEGIN { printf \"%.1f\", ($LH_TOTAL*100)/$LF_TOTAL }")
echo "[lcov] VS Code coverage: $PCT% (threshold ${THRESHOLD}%)"

# Emit GitHub Actions warning annotation if below threshold
LESS=$(awk "BEGIN { if ($PCT < $THRESHOLD) print 1; else print 0 }")
if [ "$LESS" -eq 1 ]; then
  echo "::warning ::VS Code coverage $PCT% is below threshold ${THRESHOLD}%"
fi
exit 0

