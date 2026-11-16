#!/usr/bin/env bash
# Show capture progress without touching the analysis.
set -euo pipefail
cd "$(dirname "$0")"

echo "captured files:"
ls -lh data/raw/live/*.jsonl.zst 2>/dev/null | tail -6 || echo "  (none yet)"
echo
echo "latest capture stats:"
tail -1 data/raw/live/capture.log 2>/dev/null || echo "  (no log yet)"
