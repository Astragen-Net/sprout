# Phase 0 analysis

The capture tool writes decoded pumpfun events (launches, trades, migrations,
block times) as hourly `*.jsonl.zst` files. These scripts turn them into the
pre-registered features and outcomes.

## Run

From `validation/`:

```bash
.venv/bin/python analysis/load.py --input data/raw/live
.venv/bin/python analysis/signals.py
.venv/bin/python analysis/evaluate.py
```

Outputs:

- `data/sprout.duckdb` — loaded events and `launch_features`.
- `data/processed/launch_features.parquet` — one row per launch.
- `reports/phase0_report.md` — primary/secondary results and pass/fail.
- `reports/decile_lift.png`, `reports/roc_bundle.png` — charts.

`load.py` is incremental and idempotent. It skips the file currently being
written by the capture (less than 120 seconds old) unless `--include-active` is
passed; rerun it later to pick that file up. Duplicate events are ignored by
`(sig, ix_path, event_ord)`.

## Definitions

The authoritative definitions and success bars are in
[`../PREREGISTRATION.md`](../PREREGISTRATION.md). In short:

- T+60s = `launch_slot + 150` slots; 1h/6h/24h = `+9,000 / +54,000 / +216,000`.
- `bundle_score`: share of early bought base tokens bought by wallets in slots
  with at least 4 distinct buyers.
- `rug_24h`: minimum price within 24h is at most 10% of the T+60s price.
- Primary bar: AUC ≥ 0.70, CI lower bound > 0.60, top-vs-bottom decile lift
  ≥ 1.5×, top-10% precision ≥ 1.3× base rate, n ≥ 500 on confirmation.

## Capture tool

`capture/` is a standalone Rust binary. See its `Cargo.toml`; run it with
`GRPC_URL` and `GRPC_TOKEN` in the environment:

```bash
cd capture
GRPC_URL=... GRPC_TOKEN=... CAPTURE_MINUTES=4320 CAPTURE_OUT=../data/raw/live \
  ./target/release/sprout-capture
```

It decodes legacy and v2/v3 pumpfun instructions from the official IDL
(`data/idl/pump.json`), ignores Anchor event CPIs, and separates native-SOL,
WSOL and USDC quote paths. `decode_errors` in the log counts instructions that
could not be matched to balances; it should stay at zero.

## Known gaps

- No funding-graph tracing (RPC key missing).
- No post-migration AMM trades.
- Concentration is trade-derived, not true holder balances.
- USDC/other quote mints are captured but excluded from the primary analysis.
