# Fixture

`sample.jsonl.zst` is one minute of public pumpfun capture from 2026-11-13 22:00 UTC: launches, trades, migrations and block times in the capture's JSONL schema. 278 KB compressed.

It exists to exercise the loader and feature pipeline without a 72-hour capture:

```bash
.venv/bin/python analysis/load.py --input fixtures --db data/fixture.duckdb --reset --include-active
.venv/bin/python analysis/signals.py --db data/fixture.duckdb --out data/processed/fixture.parquet
```

It is too short to produce 12-hour or 24-hour outcomes. Use it for smoke tests only.

The fixture is public on-chain data; no copyright is claimed over the underlying
data. It contains third-party token metadata and URIs (for example IPFS links);
those are not endorsed by this project.
