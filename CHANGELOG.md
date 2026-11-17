# Changelog

## [0.1.1] - 2026-11-17

- Fix first-buy decoding: base amounts now come from the user token account, not
  the newly created curve vault.
- Fix `dead_*` outcome alignment and report observed/dead cohort counts.
- Add a replay backtest with fees, slippage, horizon exits, optional stop, and
  high/rest/random/all comparisons.
- Add restart-safe per-run files, a persisted slot checkpoint, and graceful
  Ctrl-C handling.
- Do not mark truncated zstd files as ingested in `load.py`.
- Add CI, Rust/Python regression tests, `CONTRIBUTING.md`, `SECURITY.md`,
  `CITATION.cff`, issue templates, and the JSONL event schema.

## [0.1.0] - 2026-11-13

- Initial pumpfun V3 research kit: Rust gRPC capture/decoder, Python/DuckDB
  analysis, pre-registrations, reports, and one-minute fixture.
