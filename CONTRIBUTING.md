# Contributing

This is a research kit, not a product. Contributions that improve decoder
correctness, test coverage, reproducibility, or documentation are welcome.

## Before opening a pull request

From the repository root:

```bash
cargo fmt --manifest-path validation/capture/Cargo.toml -- --check
cargo clippy --manifest-path validation/capture/Cargo.toml --locked --all-targets -- -D warnings
cargo test --manifest-path validation/capture/Cargo.toml --locked

python -m unittest discover -s validation/analysis -p "test_*.py"
```

Run the fixture smoke test:

```bash
cd validation
.venv/bin/python analysis/load.py --input fixtures --db data/fixture.duckdb --reset --include-active
.venv/bin/python analysis/signals.py --db data/fixture.duckdb --out data/processed/fixture.parquet
.venv/bin/python analysis/evaluate.py --features data/processed/fixture.parquet --horizon 12h --out data/fixture_report.md
```

## Decoder changes

- Add a focused test or a fixture that exercises the changed instruction.
- Verify account positions against the public IDL or a captured mainnet
  transaction; do not rely on memory.
- Update `KNOWN_ISSUES.md` if coverage or data quality changes.
- Never commit provider tokens, `.env`, raw captures, or the IDL JSON.

## Data and claims

Published effect sizes are currently provisional; see `KNOWN_ISSUES.md`. If you
regenerate data or change feature definitions, update the reports and the data
status text rather than only the code.

## License

By contributing, you agree that your contribution is licensed under the
repository's MIT license.
