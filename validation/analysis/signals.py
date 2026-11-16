#!/usr/bin/env python3
"""Compute launch-time features and outcomes from captured pumpfun events.

Windows are **chain time** from `blocks_meta` (all captured rows have it):
  T+60s = launch block_time + 60 seconds
  1h/6h/12h/24h = +3,600 / +21,600 / +43,200 / +86,400 seconds

The earlier slot-based assumption (150 slots = 60s) was wrong: the measured
2026 slot rate is ~4.65 slots/s (~215 ms/slot), so 150 slots is ~32s. This
module corrects that and keeps slots only for the "first 5 slots" sniper rule.
"""

import argparse
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

WINDOW_SECONDS = 60
HORIZONS = {"1h": 3_600, "6h": 21_600, "12h": 43_200, "24h": 86_400}
SNIPER_SLOTS = 5
INSIDER_CREATOR_CAP = 50
INSIDER_EXPANDED_PRIOR_CAP = 50


def load(db: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect(db, read_only=True)
    launches = con.execute(
        "SELECT mint, creator, name, symbol, slot, created_at FROM launches"
    ).df()
    trades = con.execute(
        """
        SELECT mint, wallet, side, base_raw, base_decimals, quote_raw,
               quote_decimals, quote_kind, slot
        FROM trades
        WHERE quote_kind IN ('sol', 'wsol')
        """
    ).df()
    migrations = con.execute("SELECT mint, slot FROM migrations").df()
    blocks = con.execute("SELECT slot, block_time FROM blocks").df()
    con.close()
    return launches, trades, migrations, blocks


def prepare(launches, trades, migrations, blocks):
    launches = launches.sort_values("slot").drop_duplicates("mint", keep="first").copy()
    blocks = blocks.drop_duplicates("slot")
    block_times = blocks.set_index("slot")["block_time"]

    launches["launch_time"] = launches["slot"].map(block_times)
    missing_launch_times = int(launches["launch_time"].isna().sum())
    launches = launches.dropna(subset=["launch_time"]).copy()

    trades["trade_time"] = trades["slot"].map(block_times)
    trades = trades.dropna(subset=["trade_time"]).copy()
    trades["base_raw"] = pd.to_numeric(trades["base_raw"], errors="coerce")
    trades["quote_raw"] = pd.to_numeric(trades["quote_raw"], errors="coerce")
    trades = trades.dropna(subset=["base_raw", "quote_raw"]).copy()
    trades["base_ui"] = trades["base_raw"] / (10.0 ** trades["base_decimals"])
    trades["quote_ui"] = trades["quote_raw"] / (10.0 ** trades["quote_decimals"])
    trades = trades[trades["base_ui"] > 0].copy()
    trades["price"] = trades["quote_ui"] / trades["base_ui"]
    trades = trades[trades["price"] > 0].copy()

    launch_slots = launches.set_index("mint")["slot"]
    launch_times = launches.set_index("mint")["launch_time"]
    trades["launch_slot"] = trades["mint"].map(launch_slots)
    trades["launch_time"] = trades["mint"].map(launch_times)
    trades = trades.dropna(subset=["launch_slot", "launch_time"]).copy()
    trades["rel_slot"] = (trades["slot"] - trades["launch_slot"]).astype("int64")
    trades["rel_seconds"] = (trades["trade_time"] - trades["launch_time"]).astype("int64")
    trades = trades[trades["rel_seconds"] >= 0].copy()

    migrations = migrations.copy()
    migrations["mig_time"] = migrations["slot"].map(block_times)
    migrations["launch_time"] = migrations["mint"].map(launch_times)
    migrations = migrations.dropna(subset=["mig_time", "launch_time"])
    migrations["rel_seconds"] = (migrations["mig_time"] - migrations["launch_time"]).astype("int64")

    return launches, trades, migrations, launch_slots, launch_times, missing_launch_times


def add_early_features(features, early, early_buy, base_by_mint):
    features["early_buy_base"] = base_by_mint
    features["early_trades"] = early.groupby("mint").size()
    features["early_buyers"] = early_buy.groupby("mint")["wallet"].nunique()
    features["early_volume_sol"] = early.groupby("mint")["quote_ui"].sum()
    features["early_buy_volume_sol"] = early_buy.groupby("mint")["quote_ui"].sum()

    def bundle_score(threshold: int) -> pd.Series:
        slot_buyers = (
            early_buy.groupby(["mint", "slot"])["wallet"]
            .nunique()
            .reset_index(name="buyers")
        )
        flagged = slot_buyers[slot_buyers["buyers"] >= threshold][["mint", "slot"]]
        if flagged.empty:
            return pd.Series(0.0, index=base_by_mint.index)
        bundle = early_buy.merge(flagged, on=["mint", "slot"], how="inner")
        base = bundle.groupby("mint")["base_ui"].sum()
        return (base / base_by_mint).reindex(base_by_mint.index).fillna(0).clip(0, 1)

    features["bundle_score"] = bundle_score(4)
    features["bundle_score_3"] = bundle_score(3)

    sniper_base = early_buy[early_buy["rel_slot"] <= SNIPER_SLOTS].groupby("mint")["base_ui"].sum()
    features["sniper_score"] = (
        (sniper_base / base_by_mint).reindex(base_by_mint.index).fillna(0).clip(0, 1)
    )

    signed = early.copy()
    signed["signed_base"] = np.where(signed["side"] == "buy", signed["base_ui"], -signed["base_ui"])
    positions = signed.groupby(["mint", "wallet"])["signed_base"].sum().reset_index()
    positions = positions[positions["signed_base"] > 0]
    positions = positions.sort_values(["mint", "signed_base"], ascending=[True, False])
    top10 = positions.groupby("mint").head(10).groupby("mint")["signed_base"].sum()
    features["concentration_top10"] = (
        (top10 / base_by_mint).reindex(base_by_mint.index).fillna(0).clip(0, 1)
    )
    return features


def add_insider(features, launches, early_buy, base_by_mint):
    creator_counts = launches["creator"].value_counts()
    eligible = creator_counts[creator_counts <= INSIDER_CREATOR_CAP].index
    small = launches[launches["creator"].isin(eligible)]

    prior = small[["mint", "creator", "slot"]].merge(
        small[["mint", "creator", "slot"]].rename(
            columns={"mint": "prior_mint", "slot": "prior_slot"}
        ),
        on="creator",
        how="inner",
    )
    prior = prior[prior["prior_slot"] < prior["slot"]][["mint", "prior_mint"]].drop_duplicates()

    buyers_by_mint = (
        early_buy[["mint", "wallet"]]
        .drop_duplicates()
        .rename(columns={"mint": "prior_mint"})
    )
    insider_wallets = (
        prior.merge(buyers_by_mint, on="prior_mint")[["mint", "wallet"]]
        .drop_duplicates()
    )
    insider_buy = early_buy.merge(insider_wallets, on=["mint", "wallet"], how="inner")
    insider_base = insider_buy.groupby("mint")["base_ui"].sum()

    score = (insider_base / base_by_mint).reindex(base_by_mint.index).fillna(0).clip(0, 1)
    known = pd.Index(prior["mint"].unique())
    features["insider_score"] = score
    features["insider_known"] = features.index.isin(known)
    features.loc[~features["insider_known"], "insider_score"] = np.nan
    return features


def add_insider_expanded(features, launches, early_buy, base_by_mint):
    pairs: list[tuple[str, str]] = []
    for _, group in launches.groupby("creator", sort=False):
        group = group.sort_values("slot")
        mints = group["mint"].tolist()
        for index, mint in enumerate(mints):
            start = max(0, index - INSIDER_EXPANDED_PRIOR_CAP)
            for prior in mints[start:index]:
                pairs.append((mint, prior))

    if not pairs:
        features["insider_score_expanded"] = np.nan
        features["insider_score_2plus"] = np.nan
        features["insider_known_expanded"] = False
        return features

    pair_frame = pd.DataFrame(pairs, columns=["mint", "prior_mint"])
    buyers = (
        early_buy[["mint", "wallet"]]
        .drop_duplicates()
        .rename(columns={"mint": "prior_mint"})
    )
    pair_buyers = pair_frame.merge(buyers, on="prior_mint", how="inner")
    repeat = (
        pair_buyers.groupby(["mint", "wallet"])["prior_mint"]
        .nunique()
        .reset_index(name="repeat_count")
    )
    insider_buy = early_buy.merge(repeat, on=["mint", "wallet"], how="inner")
    expanded = insider_buy[insider_buy["repeat_count"] >= 1].groupby("mint")["base_ui"].sum()
    two_plus = insider_buy[insider_buy["repeat_count"] >= 2].groupby("mint")["base_ui"].sum()

    features["insider_score_expanded"] = (
        (expanded / base_by_mint).reindex(base_by_mint.index).fillna(0).clip(0, 1)
    )
    features["insider_score_2plus"] = (
        (two_plus / base_by_mint).reindex(base_by_mint.index).fillna(0).clip(0, 1)
    )
    known = pd.Index(pair_frame["mint"].unique())
    features["insider_known_expanded"] = features.index.isin(known)
    features.loc[~features["insider_known_expanded"], "insider_score_expanded"] = np.nan
    features.loc[~features["insider_known_expanded"], "insider_score_2plus"] = np.nan
    return features


def add_outcomes(features, trades, migrations):
    price_60 = (
        trades[trades["rel_seconds"] <= WINDOW_SECONDS]
        .sort_values(["mint", "trade_time"])
        .groupby("mint")["price"]
        .last()
    )
    features["price_60s"] = price_60

    after = trades[trades["rel_seconds"] > WINDOW_SECONDS]
    capture_max_time = int(max(int(trades["trade_time"].max()), int(features["launch_time"].max())))
    features["capture_max_time"] = capture_max_time

    for label, seconds in HORIZONS.items():
        window = after[after["rel_seconds"] <= seconds]
        last = window.sort_values(["mint", "trade_time"]).groupby("mint")["price"].last()
        minimum = window.groupby("mint")["price"].min()
        maximum = window.groupby("mint")["price"].max()

        features[f"price_{label}"] = last
        features[f"min_price_{label}"] = minimum
        features[f"max_price_{label}"] = maximum
        features[f"dead_{label}"] = minimum.isna()
        features[f"censored_{label}"] = features["launch_time"] + seconds > capture_max_time

        valid = features["price_60s"].notna() & minimum.reindex(features.index).notna()
        features[f"rug_{label}"] = (
            (minimum.reindex(features.index) <= 0.1 * features["price_60s"]).where(valid)
        )
        features[f"terminal_rug_{label}"] = (
            (last.reindex(features.index) <= 0.1 * features["price_60s"])
            .where(features["price_60s"].notna() & last.reindex(features.index).notna())
        )
        features[f"drawdown_{label}"] = (
            minimum.reindex(features.index) / features["price_60s"] - 1
        )
        features[f"peak_multiple_{label}"] = (
            maximum.reindex(features.index) / features["price_60s"]
        )

    graduated = migrations[
        (migrations["rel_seconds"] >= 0) & (migrations["rel_seconds"] <= HORIZONS["24h"])
    ].groupby("mint").size()
    features["graduated_24h"] = features.index.isin(graduated.index).astype(bool)
    return features


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sprout.duckdb")
    parser.add_argument("--out", default="data/processed/launch_features.parquet")
    parser.add_argument(
        "--stats-until",
        default=None,
        help="ISO timestamp; restrict printed statistics (not the parquet)",
    )
    args = parser.parse_args()

    launches, trades, migrations, blocks = load(args.db)
    if launches.empty or trades.empty:
        print("no launches/trades loaded; run load.py first")
        return 2

    launches, trades, migrations, launch_slots, launch_times, missing_launch_times = prepare(
        launches, trades, migrations, blocks
    )
    early = trades[trades["rel_seconds"] <= WINDOW_SECONDS]
    early_buy = early[early["side"] == "buy"]
    base_by_mint = early_buy.groupby("mint")["base_ui"].sum()

    features = launches.set_index("mint")[
        ["creator", "name", "symbol", "slot", "launch_time"]
    ].copy()
    features["creator_prior_launches"] = (
        launches.sort_values("slot")
        .assign(prior=lambda frame: frame.groupby("creator").cumcount())
        .set_index("mint")["prior"]
    )

    features = add_early_features(features, early, early_buy, base_by_mint)
    features = add_insider(features, launches, early_buy, base_by_mint)
    features = add_insider_expanded(features, launches, early_buy, base_by_mint)
    features = add_outcomes(features, trades, migrations)

    features = features.reset_index()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(args.out, index=False)

    con = duckdb.connect(args.db)
    con.register("features_df", features)
    con.execute("CREATE OR REPLACE TABLE launch_features AS SELECT * FROM features_df")
    con.close()

    print(f"launches: {len(features):,} (missing block time: {missing_launch_times:,})")
    stats_frame = features
    if args.stats_until:
        cutoff = pd.Timestamp(args.stats_until, tz="UTC").timestamp()
        stats_frame = features[features["launch_time"] < cutoff]
        print(f"  stats restricted to launch_time < {args.stats_until} ({len(stats_frame):,} launches)")
    print(f"  with early trades: {int((stats_frame['early_trades'].fillna(0) > 0).sum()):,}")
    for label in HORIZONS:
        eligible = stats_frame[
            (~stats_frame[f"censored_{label}"].fillna(True))
            & stats_frame["price_60s"].notna()
            & (stats_frame["early_trades"].fillna(0) > 0)
            & stats_frame[f"rug_{label}"].notna()
        ]
        print(
            f"  {label}: eligible={len(eligible):,} "
            f"rug_rate={eligible[f'rug_{label}'].mean():.2%} "
            f"flagged={int((eligible['bundle_score'] > 0).sum()):,}"
        )
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
