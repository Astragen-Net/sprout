# pumpfun V3 research kit

A reproducible research kit for pump.fun V3: a Rust gRPC capture/decoder, a Python/DuckDB validation pipeline, and the pre-registered findings from 72 hours of mainnet data (122,660 launches, 7.55M trades, zero decode errors).

**Research and educational project. Not financial advice. No warranty. Not affiliated with pump.fun.**

## Findings at a glance

| Test | Result |
|---|---|
| Same-slot bundle score → rug | **Inverted** (12h interim AUC 0.452; 24h AUC 0.409, n=203; flagged 1.6% vs 18.4% unflagged) |
| Insider repeat-buyer network → 24h rug | **Failed the bar** (AUC 0.649 vs 0.65; precision 1.26× vs 1.30×) |
| Creator dev-buy / fast-sell / prior dump → 24h rug | **Inverted** (AUC 0.286–0.448); no feature reached 0.70 |
| Bundle negative control | 0.448 (inverted, as expected) |

The short version: same-slot bundle and sniper signals measure **demand**, not coordination; the insider network is real but too broad to clear a product bar; direct creator dev-buys and fast sells predict **survival** at 24h. See [FINDINGS.md](FINDINGS.md) for the method, numbers and limitations.

## Repository layout

```
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
CAPTURE_MINUTES=5 CAPTURE_OUT=../data/raw ./target/release/sprout-capture
```

`CAPTURE_MINUTES=0` runs until interrupted. Files rotate hourly and are zstd-compressed JSONL.

### Analyse

```bash
cd validation
python3.14 -m venv .venv
.venv/bin/pip install -r analysis/requirements.txt
.venv/bin/python analysis/load.py --input data/raw --db data/sprout.duckdb --reset --include-active
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

## What is not included

- The raw 72-hour capture (~4.2 GB) and the full launch dataset.
- The pump.fun IDL JSON; it has no explicit license, so fetch it from the public `pump-fun/pump-public-docs` repository if you need it. The decoder uses public protocol facts.
- Any code from a prior proprietary codebase. See [PROVENANCE.md](PROVENANCE.md).

## License

MIT. Copyright (c) 2026 Rahul Jaguste. See [LICENSE](LICENSE).
