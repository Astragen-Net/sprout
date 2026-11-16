#!/usr/bin/env bash
# Run after the capture has produced 24h outcomes for the fresh window
# (launch_time >= 2026-11-15T00:00:00Z and launch_time + 24h <= capture end).
set -euo pipefail
cd "$(dirname "$0")"

.venv/bin/python analysis/load.py --input data/raw/live
.venv/bin/python analysis/signals.py
.venv/bin/python analysis/v2_evaluate.py

echo
echo "report: $(pwd)/reports/phase0_v2.md"
