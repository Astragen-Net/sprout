#!/usr/bin/env python3
"""Load captured pumpfun JSONL.zst events into DuckDB.

Idempotent: files already ingested at the same size/mtime are skipped, and
event keys are de-duplicated with INSERT OR IGNORE. Files still being written
by the capture process are skipped unless --include-active is passed.
"""

import argparse
import io
import json
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd
import zstandard as zstd

SCHEMA = """
CREATE TABLE IF NOT EXISTS launches (
  mint VARCHAR, curve VARCHAR, creator VARCHAR, name VARCHAR, symbol VARCHAR, uri VARCHAR,
  slot BIGINT, tx_index BIGINT, ix_path INTEGER, event_ord INTEGER, sig VARCHAR, created_at BIGINT,
  PRIMARY KEY (sig, ix_path, event_ord)
);
CREATE TABLE IF NOT EXISTS trades (
  mint VARCHAR, wallet VARCHAR, curve VARCHAR, side VARCHAR,
  base_raw VARCHAR, base_decimals INTEGER, quote_raw VARCHAR, quote_decimals INTEGER,
  quote_mint VARCHAR, quote_kind VARCHAR,
  slot BIGINT, tx_index BIGINT, ix_path INTEGER, event_ord INTEGER, sig VARCHAR, created_at BIGINT,
  PRIMARY KEY (sig, ix_path, event_ord)
);
CREATE TABLE IF NOT EXISTS migrations (
  mint VARCHAR, pool VARCHAR,
  slot BIGINT, tx_index BIGINT, ix_path INTEGER, event_ord INTEGER, sig VARCHAR, created_at BIGINT,
  PRIMARY KEY (sig, ix_path, event_ord)
);
CREATE TABLE IF NOT EXISTS blocks (
  slot BIGINT PRIMARY KEY, block_time BIGINT
);
CREATE TABLE IF NOT EXISTS ingested_files (
  path VARCHAR PRIMARY KEY, size BIGINT, mtime DOUBLE, loaded_at TIMESTAMP
);
"""

COLUMNS = {
    "launch": [
        "mint", "curve", "creator", "name", "symbol", "uri",
        "slot", "tx_index", "ix_path", "event_ord", "sig", "created_at",
    ],
    "trade": [
        "mint", "wallet", "curve", "side",
        "base_raw", "base_decimals", "quote_raw", "quote_decimals",
        "quote_mint", "quote_kind",
        "slot", "tx_index", "ix_path", "event_ord", "sig", "created_at",
    ],
    "migration": [
        "mint", "pool", "slot", "tx_index", "ix_path", "event_ord", "sig", "created_at",
    ],
    "block": ["slot", "block_time"],
}

TABLE_FOR_KIND = {
    "launch": "launches",
    "trade": "trades",
    "migration": "migrations",
    "block": "blocks",
}

BATCH_SIZE = 25_000
ACTIVE_SECONDS = 120


def insert_batch(con: duckdb.DuckDBPyConnection, table: str, rows: list[dict], columns: list[str]) -> None:
    if not rows:
        return
    frame = pd.DataFrame(rows, columns=columns)
    con.register("_batch", frame)
    column_list = ", ".join(columns)
    con.execute(
        f"INSERT OR IGNORE INTO {table} ({column_list}) "
        f"SELECT {column_list} FROM _batch"
    )
    con.unregister("_batch")
    rows.clear()


def ingest_file(con: duckdb.DuckDBPyConnection, path: Path) -> dict[str, int]:
    counts = {"launch": 0, "trade": 0, "migration": 0, "block": 0, "bad": 0}
    batches = {kind: [] for kind in COLUMNS}

    with open(path, "rb") as handle:
        reader = zstd.ZstdDecompressor().stream_reader(handle)
        text = io.TextIOWrapper(reader, encoding="utf-8", errors="replace")
        try:
            for line in text:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    counts["bad"] += 1
                    continue
                kind = event.get("kind")
                if kind not in COLUMNS:
                    counts["bad"] += 1
                    continue
                columns = COLUMNS[kind]
                batches[kind].append({column: event.get(column) for column in columns})
                counts[kind] += 1
                if len(batches[kind]) >= BATCH_SIZE:
                    insert_batch(con, TABLE_FOR_KIND[kind], batches[kind], columns)
        except (zstd.ZstdError, UnicodeDecodeError) as error:
            print(f"  warning: truncated/corrupt stream in {path.name}: {error}", file=sys.stderr)

    for kind, rows in batches.items():
        insert_batch(con, TABLE_FOR_KIND[kind], rows, COLUMNS[kind])
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sprout.duckdb")
    parser.add_argument("--input", default="data/raw/live")
    parser.add_argument("--include-active", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"input directory missing: {input_dir}", file=sys.stderr)
        return 2

    con = duckdb.connect(str(db_path))
    con.execute("SET threads = 4")
    if args.reset:
        for table in ("launches", "trades", "migrations", "blocks", "ingested_files"):
            con.execute(f"DROP TABLE IF EXISTS {table}")
    for statement in SCHEMA.strip().split(";"):
        statement = statement.strip()
        if statement:
            con.execute(statement)

    files = sorted(input_dir.glob("*.jsonl.zst"))
    if not files:
        print(f"no .jsonl.zst files in {input_dir}", file=sys.stderr)
        return 2

    now = time.time()
    ingested = 0
    skipped = 0
    totals = {"launch": 0, "trade": 0, "migration": 0, "block": 0, "bad": 0}

    for path in files:
        stat = path.stat()
        row = con.execute(
            "SELECT size, mtime FROM ingested_files WHERE path = ?", [str(path)]
        ).fetchone()
        if row and int(row[0]) == stat.st_size and abs(float(row[1]) - stat.st_mtime) < 1:
            skipped += 1
            continue
        if not args.include_active and (now - stat.st_mtime) < ACTIVE_SECONDS:
            skipped += 1
            continue

        print(f"loading {path.name} ({stat.st_size / 1_000_000:.1f} MB)")
        counts = ingest_file(con, path)
        con.execute(
            "INSERT OR REPLACE INTO ingested_files VALUES (?, ?, ?, now())",
            [str(path), stat.st_size, stat.st_mtime],
        )
        for key, value in counts.items():
            totals[key] += value
        ingested += 1

    print(
        f"ingested {ingested} files, skipped {skipped}: "
        f"launches={totals['launch']} trades={totals['trade']} "
        f"migrations={totals['migration']} blocks={totals['block']} bad={totals['bad']}"
    )
    for table in ("launches", "trades", "migrations", "blocks"):
        count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count:,} rows")
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
