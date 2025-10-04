#!/usr/bin/env sh
# List near-threshold and worst files from an lcov.info
# Usage: scripts/lcov-near.sh <lcov.info> <threshold_pct> [window_pct] [top]

set -eu
LCOV_FILE="$1"
THRESHOLD="${2:-80}"
WINDOW="${3:-5}"
TOP="${4:-20}"

if [ ! -f "$LCOV_FILE" ]; then
  echo "[lcov-near] file not found: $LCOV_FILE" 1>&2
  exit 0
fi

# Print quick totals (lines found/hit) and coverage
LF_TOTAL=$(awk -F: '/^LF:/{s+=$2} END{print s+0}' "$LCOV_FILE")
LH_TOTAL=$(awk -F: '/^LH:/{s+=$2} END{print s+0}' "$LCOV_FILE")
if [ "$LF_TOTAL" -gt 0 ]; then
  PCT=$(awk "BEGIN { printf \"%.1f\", ($LH_TOTAL*100)/$LF_TOTAL }")
  echo "[lcov-near] VS Code coverage: $PCT% (LF=$LF_TOTAL, LH=$LH_TOTAL)"
fi

awk -v TH="$THRESHOLD" -v WIN="$WINDOW" -v TOPN="$TOP" '
BEGIN{FS=":"}
  /^SF:/ { if (cur!="") { files[cur]=cov; } cur=$2; lf=0; lh=0; cov=-1 }
  /^LF:/ { lf=$2+0 }
  /^LH:/ { lh=$2+0 }
  /^end_of_record/ {
     if (lf>0) { cov=(lh*100.0)/lf } else { cov=0 }
     files[cur]=cov
     cur=""
  }
END{
  # Collect
  for (f in files) {
    cov=files[f]
    if (cov<0) continue
    idx[n]=f; n++
  }
  # Sort ascending by coverage
  for (i=0;i<n;i++) for (j=i+1;j<n;j++) {
    if (files[idx[i]]>files[idx[j]]) { t=idx[i]; idx[i]=idx[j]; idx[j]=t }
  }
  # Print summary
  print "[lcov-near] threshold:", TH"%", "window:", WIN"%", "top:", TOPN
  # Near-below list
  print "\n[lcov-near] Near-below (within window, below threshold):"
  cnt=0
  for (i=0;i<n;i++) {
    cov=files[idx[i]]
    if (cov>=TH) continue
    if (cov<TH && cov>=TH-WIN) {
      printf(" - %.1f%% < %.0f%% — %s\n", cov, TH, idx[i])
      cnt++
      if (cnt>=TOPN) break
    }
  }
  if (cnt==0) print " (none)"
  # Worst list
  print "\n[lcov-near] Worst files (lowest coverage):"
  cnt=0
  for (i=0;i<n && cnt<TOPN;i++) {
    cov=files[idx[i]]
    printf(" - %.1f%% — %s\n", cov, idx[i])
    cnt++
  }
}
' "$LCOV_FILE"
