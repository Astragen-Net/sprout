# pumpfun V3 research kit

A reproducible research kit for pump.fun V3: a Rust gRPC capture/decoder, a Python/DuckDB validation pipeline, and the pre-registered findings from 72 hours of mainnet data (~122k launches, 7.5M deduped trades, zero balance-lookup decode errors).

**Research and educational project. Not financial advice. No warranty. Not affiliated with pump.fun.**

> **Status: research-grade; effect sizes are provisional.** The 72-hour capture predates the first-buy decoder fix. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md). The stop/pivot decision is robust, but do not cite the effect sizes as final until the data is regenerated.

## Findings at a glance

| Test | Result |
|---|---|
| Same-slot bundle score → rug | **Inverted** (full 24h AUC 0.450, n=7,896; 12h interim 0.452; flagged 1.9% vs 22.5% unflagged) |
| Insider repeat-buyer network → 24h rug | **Failed the bar** (AUC 0.649 vs 0.65; precision 1.26× vs 1.30×) |
| Creator dev-buy / fast-sell / prior dump → 24h rug | **Inverted** (AUC 0.286–0.448); no feature reached 0.70 |
| Bundle negative control | 0.448 (inverted, as expected) |
| Replay backtest, insider ≥0.9, 24h hold, fees/slippage | **Negative** (mean -34.9%, median -67.0%, win 13.9%; zero-cost/stop/1h variants also negative) |
| Post-T+60 5–60s dump harness | **No candidate** (best insider 0.646 at 60s; creator/dev features inverted) |

The short version: same-slot bundle and sniper signals measure **demand**, not coordination; the insider network is real but too broad to clear a product bar; direct creator dev-buys and fast sells predict **survival** at 24h. See [FINDINGS.md](FINDINGS.md) for the method, numbers and limitations, and [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the data-quality caveats. The table above is provisional.

## Repository layout

```
KNOWN_ISSUES.md       Data status, decoder limitation, coverage caveats
CONTRIBUTING.md       Development and pull-request checklist
SECURITY.md           Secret handling and vulnerability reporting
CHANGELOG.md
CITATION.cff
docs/EVENT_SCHEMA.md  JSONL event schema and identifiers
validation/
  capture/            Rust gRPC capture + pumpfun decoder (legacy, V2, V3)
  analysis/           Python/DuckDB loader, feature computation, evaluation
  fixtures/           One-minute sample capture (public on-chain events)
  PREREGISTRATION.md  v1 hypothesis and frozen success bars
  PREREGISTRATION_V2.md
  reports/            Pre-registered results, exploratory dev-dump test, summary
  run_analysis.sh     Full-capture analysis runner (expects data/raw/live)
  run_v2.sh           v2 fresh-window runner
  status.sh           Capture progress
```

## Quickstart

### Prerequisites

- Rust stable (the capture crate uses edition 2024)
- Python 3.14
- A Yellowstone gRPC endpoint and token from a provider such as Shyft, Helius or Subglow. The project does not include a token.

### Build the capture tool

```bash
cd validation/capture
cargo build --release
```

### Capture five minutes

```bash
export GRPC_URL="https://your-geyser-endpoint"
export GRPC_TOKEN="your-provider-token"
mkdir -p ../data/raw/live
CAPTURE_MINUTES=5 CAPTURE_OUT=../data/raw/live ./target/release/sprout-capture \
  2> ../data/raw/live/capture.log
```

`CAPTURE_MINUTES=0` runs until interrupted. Files rotate hourly and are zstd-compressed JSONL. Restarts resume from `data/raw/live/checkpoint` and write a new per-run file, so an existing hour is not truncated. Use Ctrl-C for a graceful stop.

### Analyse

```bash
cd validation
python3.14 -m venv .venv
.venv/bin/pip install -r analysis/requirements.txt
.venv/bin/python analysis/load.py --input data/raw/live --db data/sprout.duckdb --reset --include-active
.venv/bin/python analysis/signals.py --db data/sprout.duckdb
.venv/bin/python analysis/evaluate.py --horizon 12h --out reports/local_report.md
```

A five-minute capture exercises the loader and features, but has no 12/24-hour outcomes. A meaningful backtest needs at least 12–24 hours of capture; the published run used 72 hours.

### Run the included fixture

```bash
cd validation
.venv/bin/python analysis/load.py --input fixtures --db data/fixture.duckdb --reset --include-active
.venv/bin/python analysis/signals.py --db data/fixture.duckdb --out data/processed/fixture.parquet
.venv/bin/python analysis/evaluate.py --features data/processed/fixture.parquet --horizon 12h --out reports/fixture_report.md
```

The fixture is one minute of public pumpfun events; it verifies the pipeline, not outcomes.

### Replay backtest

After a full capture and `signals.py`:

```bash
cd validation
.venv/bin/python analysis/replay_backtest.py
```

It enters at the first trade after T+60s, exits at the horizon (default 24h), applies fees/slippage to both sides, and compares the high-signal cohort with the rest, a random sample, and all launches. See [reports/replay_backtest.md](validation/reports/replay_backtest.md). The fixture is too short for this; it needs a multi-hour capture. Results are exploratory and provisional.

### Short-horizon dump research

```bash
.venv/bin/python analysis/short_horizon_dump.py
```

This evaluates launch-time and creator/dev features against 5/15/30/60-second dumps after T+60s. It reports no candidate: the best feature is `insider_score` at 60s (AUC 0.646, 95% CI 0.634–0.657); creator/dev features are inverted. See [reports/short_horizon_dump.md](validation/reports/short_horizon_dump.md). This is a post-T+60 harness; the first-5s dev-dump pattern would need a launch-anchored variant.

## What is not included

- The raw 72-hour capture (~4.2 GB) and the full launch dataset.
- Raw transactions. The capture stores decoded events only, so an old capture cannot be re-decoded with a fixed decoder; see [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
- The pump.fun IDL JSON; it has no explicit license, so fetch it from the public `pump-fun/pump-public-docs` repository if you need it. The decoder uses public protocol facts.
- Any code from a prior proprietary codebase. See [PROVENANCE.md](PROVENANCE.md).

## License

MIT. Copyright (c) 2026 Rahul Jaguste. See [LICENSE](LICENSE).
