#!/usr/bin/env bash
# Load the live capture, compute launch features, and evaluate Phase 0.
set -euo pipefail
cd "$(dirname "$0")"

.venv/bin/python analysis/load.py --input data/raw/live
.venv/bin/python analysis/signals.py
.venv/bin/python analysis/evaluate.py

echo
echo "report: $(pwd)/reports/phase0_report.md"
echo "charts: $(pwd)/reports/decile_lift.png $(pwd)/reports/roc_bundle.png"
