# Phase 0 analysis

> **Status: research-grade; effect sizes are provisional.** The published
> capture predates the first-buy decoder fix; see
> [`../../KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md). Regenerate the data with the
> fixed decoder before citing the numbers.

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
- `reports/phase0_v1_full_24h.md` — generated full-dataset v1 24h report.
- `reports/phase0_v2.md` — fresh-window v2 report (`v2_evaluate.py`).
- `reports/replay_backtest.md` — replay backtest report (`replay_backtest.py`).
- `reports/decile_lift.png`, `reports/roc_bundle.png` — charts.

Replay backtest (requires a full capture, not the one-minute fixture):

```bash
.venv/bin/python analysis/replay_backtest.py
.venv/bin/python analysis/replay_backtest.py --horizon 1h --stop-loss 0.5
.venv/bin/python analysis/replay_backtest.py --signal bundle_score --threshold 0
```

`load.py` is incremental and idempotent. It skips the file currently being
written by the capture (less than 120 seconds old) unless `--include-active` is
passed; rerun it later to pick that file up. Duplicate events are ignored by
`(sig, ix_path, event_ord)`. A truncated or corrupt zstd stream is loaded up to
the error but is not marked ingested, so the next run retries it.

## Definitions

The authoritative definitions and success bars are in
[`../PREREGISTRATION.md`](../PREREGISTRATION.md). In short:

- T+60s = launch `block_time` + 60 seconds (chain time from `blocks_meta`);
  1h/6h/12h/24h = `+3,600 / +21,600 / +43,200 / +86,400` seconds. This
  supersedes the original slot-based definition in Amendment 2 of
  [`../PREREGISTRATION.md`](../PREREGISTRATION.md).
- `bundle_score`: share of early bought base tokens bought by wallets in slots
  with at least 4 distinct buyers.
- `rug_24h`: minimum price within 24h is at most 10% of the T+60s price.
- Dead launches (no post-T+60s trade) are excluded from price-based rug AUC and
  reported separately.
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

It decodes legacy and v2/v3 pumpfun instructions using hardcoded discriminators
and account layouts verified against the public IDL (the IDL JSON is not
redistributed in this repository). It ignores Anchor event CPIs and separates
native-SOL, WSOL and USDC quote paths. `decode_errors` counts instructions that
could not be matched to balances; `zero_delta` counts recognized trades with a
zero balance delta, and `ignored` counts unhandled discriminators. A zero
`decode_errors` value does not by itself mean complete trade coverage.

## Tests

```bash
.venv/bin/python -m unittest discover -s analysis -p 'test_*.py' -v
cd capture && cargo test --locked
```

## Known gaps

- The published capture predates the first-buy decoder fix; see
  [`../../KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md). Old captures store decoded
  events only and cannot be re-decoded.
- No funding-graph tracing (RPC key missing).
- No post-migration AMM trades.
- Concentration is trade-derived, not true holder balances.
- USDC/other quote mints are captured but excluded from the primary analysis.
- `multi_hop_curve_swap` and `migrate_bonding_curve_creator` are not decoded.
- No raw-transaction capture mode; old captures store decoded events only.
- The capture now writes a per-run hourly file and persists a checkpoint, so
  restarts are safe. Captures made before this fix may contain a truncated hour.
