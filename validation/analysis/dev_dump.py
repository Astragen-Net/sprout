#!/usr/bin/env python3
"""Exploratory: creator dev-buy / launch-and-dump features vs 24h rug.

This is NOT a pre-registered gate. It uses the existing 122k-launch dataset
(already used by v1/v2) to test the pattern described by the pumpfunbots
research: dev-buy in the create transaction, creator sells within seconds,
prior creator dump history, and a sell-only wallet network.

If a feature is materially stronger than v2 (AUC >= 0.70, CI lower > 0.60),
the next step is a fresh pre-registered capture. Otherwise, stop.
"""

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import bootstrap_auc, cohort_metrics, decile_table  # noqa: E402

DB = "data/sprout.duckdb"
FEATURES = "data/processed/launch_features.parquet"
OUT = "reports/dev_dump_exploratory.md"
PRIOR_DUMP_CAP = 50


def load(con):
    launches = con.execute(
        """
        SELECT l.mint, l.creator, l.slot, l.sig, b.block_time AS launch_time
        FROM launches l LEFT JOIN blocks b USING(slot)
        """
    ).df()
    early = con.execute(
        """
        SELECT * FROM (
          SELECT t.mint, t.wallet, t.side, t.sig, t.slot,
                 t.base_raw::DOUBLE / pow(10, t.base_decimals) AS base_ui,
                 b.block_time - lb.block_time AS rel_seconds,
                 l.creator, l.sig AS create_sig
          FROM trades t
          JOIN launches l ON l.mint = t.mint
          JOIN blocks b ON b.slot = t.slot
          JOIN blocks lb ON lb.slot = l.slot
          WHERE t.quote_kind IN ('sol', 'wsol')
        )
        WHERE rel_seconds >= 0 AND rel_seconds <= 60
        """
    ).df()
    features = pd.read_parquet(FEATURES)[
        [
            "mint", "launch_time", "censored_24h", "price_60s",
            "early_trades", "rug_24h", "bundle_score", "insider_score",
        ]
    ]
    return launches, early, features


def build_features(launches, early):
    early["is_creator"] = early["wallet"] == early["creator"]
    buys = early["side"] == "buy"
    sells = early["side"] == "sell"

    base_buy = early[buys].groupby("mint")["base_ui"].sum()
    base_sell = early[sells].groupby("mint")["base_ui"].sum()
    creator_buy = early[early["is_creator"] & buys].groupby("mint")["base_ui"].sum()
    creator_sell = early[early["is_creator"] & sells].groupby("mint")["base_ui"].sum()
    create_tx_buy = early[
        early["is_creator"] & buys & (early["sig"] == early["create_sig"])
    ].groupby("mint")["base_ui"].sum()
    sold_5 = (
        early[early["is_creator"] & sells & (early["rel_seconds"] <= 5)]
        .groupby("mint")
        .size()
    )
    sold_60 = early[early["is_creator"] & sells].groupby("mint").size()

    dev = pd.DataFrame(index=base_buy.index)
    dev.index.name = "mint"
    dev["creator_buy_share"] = (creator_buy / base_buy).clip(0, 1)
    dev["creator_create_buy_share"] = (create_tx_buy / base_buy).clip(0, 1)
    dev["creator_sell_share"] = (creator_sell / base_buy).clip(0, 1)
    dev["creator_net_share"] = (creator_buy - creator_sell) / base_buy
    dev["creator_sold_5s"] = sold_5.reindex(dev.index).fillna(0).gt(0)
    dev["creator_sold_60s"] = sold_60.reindex(dev.index).fillna(0).gt(0)
    dev["creator_create_buy"] = create_tx_buy.reindex(dev.index).fillna(0).gt(0)

    stats = launches[["mint", "creator", "slot"]].copy()
    stats["sold_5s"] = stats["mint"].map(dev["creator_sold_5s"]).fillna(False).astype(int)
    stats = stats.sort_values(["creator", "slot"])
    stats["prior_launches"] = stats.groupby("creator").cumcount()
    stats["prior_sold"] = (
        stats.groupby("creator")["sold_5s"].cumsum() - stats["sold_5s"]
    )
    stats["creator_prior_dump_rate"] = np.where(
        stats["prior_launches"] > 0,
        stats["prior_sold"] / stats["prior_launches"],
        np.nan,
    )
    dev = dev.join(
        stats.set_index("mint")[["prior_launches", "creator_prior_dump_rate"]],
        how="left",
    )

    # Sell-only network: early sellers that bought in a prior launch by the
    # same creator and did not buy early in the current launch.
    early_buyers = early[buys][["mint", "wallet"]].drop_duplicates()
    pairs: list[tuple[str, str]] = []
    for _, group in launches.groupby("creator", sort=False):
        group = group.sort_values("slot")
        mints = group["mint"].tolist()
        for index, mint in enumerate(mints):
            start = max(0, index - PRIOR_DUMP_CAP)
            for prior in mints[start:index]:
                pairs.append((mint, prior))
    if pairs:
        pair_frame = pd.DataFrame(pairs, columns=["mint", "prior_mint"])
        prior_buyers = (
            pair_frame.merge(
                early_buyers.rename(columns={"mint": "prior_mint"}),
                on="prior_mint",
            )[["mint", "wallet"]]
            .drop_duplicates()
        )
        sellers = early[sells][["mint", "wallet", "base_ui"]]
        sell_only = sellers.merge(prior_buyers, on=["mint", "wallet"], how="inner")
        sell_only = sell_only.merge(
            early_buyers, on=["mint", "wallet"], how="left", indicator=True
        )
        sell_only = sell_only[sell_only["_merge"] == "left_only"]
        sell_only_base = sell_only.groupby("mint")["base_ui"].sum()
        dev["sell_only_network_share"] = (
            sell_only_base / base_sell.replace(0, np.nan)
        ).reindex(dev.index).fillna(0).clip(0, 1)
    else:
        dev["sell_only_network_share"] = 0.0

    return dev


SIGNALS = [
    "creator_create_buy_share",
    "creator_create_buy",
    "creator_buy_share",
    "creator_sell_share",
    "creator_net_share",
    "creator_sold_5s",
    "creator_sold_60s",
    "creator_prior_dump_rate",
    "sell_only_network_share",
    "bundle_score",
    "insider_score",
]


def main() -> int:
    con = duckdb.connect(DB, read_only=True)
    launches, early, features = load(con)
    con.close()

    print(f"launches: {len(launches):,}; early trades: {len(early):,}")
    dev = build_features(launches, early)
    data = features.merge(dev.reset_index(), on="mint", how="left")
    eligible = data[
        (~data["censored_24h"].fillna(True))
        & data["price_60s"].notna()
        & (data["early_trades"].fillna(0) > 0)
        & data["rug_24h"].notna()
    ]
    print(f"eligible 24h: {len(eligible):,}; rug rate: {eligible['rug_24h'].mean():.1%}")

    rows = []
    for signal in SIGNALS:
        subset = eligible[[signal, "rug_24h"]].dropna()
        if len(subset) < 50 or subset["rug_24h"].nunique() < 2:
            rows.append(
                (signal, len(subset), np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan)
            )
            continue
        y = subset["rug_24h"].astype(int).to_numpy()
        x = subset[signal].astype(float).to_numpy()
        auc, low, high = bootstrap_auc(y, x)
        flagged_n, flagged_rate, unflagged_rate, lift, precision = cohort_metrics(y, x)
        rows.append((signal, len(subset), auc, low, high, flagged_n, flagged_rate, lift, precision))

    lines = [
        "# Dev-dump exploratory test (not pre-registered)\n",
        "Uses the existing 122k-launch dataset already used by v1/v2; **exploratory only**. "
        "A feature must reach AUC ≥ 0.70 with CI lower > 0.60 before a fresh pre-registered capture is justified.\n",
        f"- Eligible 24h launches: **{len(eligible):,}**",
        f"- 24h rug prevalence: **{eligible['rug_24h'].mean():.1%}**\n",
        "| Feature | n | AUC | 95% CI | Flagged n | Flagged rug | Lift | Precision multiple |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        signal, n, auc, low, high, flagged_n, flagged_rate, lift, precision = row
        def fmt(value, digits=3):
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return "n/a"
            return f"{value:.{digits}f}"
        lines.append(
            f"| {signal} | {n:,} | {fmt(auc)} | {fmt(low)}–{fmt(high)} "
            f"| {flagged_n:,} | {fmt(flagged_rate) if not isinstance(flagged_rate, float) or not np.isnan(flagged_rate) else 'n/a'} "
            f"| {fmt(lift, 2)}× | {fmt(precision, 2)}× |"
        )
    lines.append("")
    lines.append("**Caveat:** the creator wallet may not be the dev-buy wallet; the repo notes dev-buys are often paid by a sub-wallet. "
                 "This test only detects a direct creator buy. A null result does not fully rule out the pattern.\n")
    report = Path(OUT)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines))
    for row in rows:
        signal, n, auc, low, high, flagged_n, flagged_rate, lift, precision = row
        print(f"{signal:30s} n={n:6d} auc={auc:.3f} ci={low:.3f}-{high:.3f} flagged={flagged_n} lift={lift if isinstance(lift,float) else float('nan'):.2f} prec={precision if isinstance(precision,float) else float('nan'):.2f}")
    print(f"wrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
