#!/usr/bin/env python3
"""Evaluate launch-time features against 5-60 second dump labels.

This is the second-question harness: instead of the 24h rug label, it asks
whether the same launch-time features separate launches that dump within a
short window after T+60s. It is exploratory and uses the pre-fix capture; see
KNOWN_ISSUES.md.
"""

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dev_dump
from evaluate import bootstrap_auc, cohort_metrics, precision_at_top

DEFAULT_WINDOWS = "5,15,30,60"
CANDIDATE_FEATURES = [
    "bundle_score",
    "sniper_score",
    "concentration_top10",
    "insider_score",
    "creator_prior_launches",
    "early_buyers",
    "early_buy_volume_sol",
    "creator_create_buy_share",
    "creator_create_buy",
    "creator_buy_share",
    "creator_sell_share",
    "creator_net_share",
    "creator_sold_5s",
    "creator_sold_60s",
    "creator_prior_dump_rate",
    "sell_only_network_share",
]


def parse_windows(value: str) -> list[int]:
    windows = sorted({int(part) for part in value.split(",") if part.strip()})
    if not windows or any(window <= 0 for window in windows):
        raise ValueError("windows must be positive integers")
    return windows


def load_short_prices(db: str, features: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    con = duckdb.connect(db, read_only=True)
    con.register("f", features[["mint", "launch_time"]])
    selects = ",\n".join(
        f"min(price) FILTER (WHERE rel_seconds <= {60 + window}) AS min_{window}"
        for window in windows
    )
    query = f"""
        WITH t AS (
          SELECT tr.mint,
                 b.block_time - f.launch_time AS rel_seconds,
                 tr.quote_raw::DOUBLE / pow(10, tr.quote_decimals)
                   / (tr.base_raw::DOUBLE / pow(10, tr.base_decimals)) AS price
          FROM trades tr
          JOIN blocks b ON b.slot = tr.slot
          JOIN f ON f.mint = tr.mint
          WHERE tr.quote_kind IN ('sol', 'wsol')
            AND tr.base_decimals IS NOT NULL
            AND tr.quote_decimals IS NOT NULL
            AND tr.base_raw::DOUBLE > 0
            AND tr.quote_raw::DOUBLE > 0
            AND b.block_time > f.launch_time + 60
            AND b.block_time <= f.launch_time + {60 + max(windows)}
        )
        SELECT mint,
        {selects}
        FROM t
        GROUP BY mint
    """
    prices = con.execute(query).df()
    con.close()
    return prices


def attach_dev_features(
    db: str, features: pd.DataFrame, features_path: str
) -> pd.DataFrame:
    with duckdb.connect(db, read_only=True) as con:
        launches, early, _ = dev_dump.load(con, features_path)
        dev = dev_dump.build_features(launches, early).reset_index()
    return features.merge(dev, on="mint", how="left")


def add_labels(frame: pd.DataFrame, windows: list[int], drop: float) -> pd.DataFrame:
    for window in windows:
        minimum = frame[f"min_{window}"]
        frame[f"no_trade_{window}"] = minimum.isna()
        frame[f"dump_{window}"] = (
            minimum <= frame["price_60s"] * (1.0 - drop)
        ).fillna(False).astype(bool)
    return frame


def evaluate(
    frame: pd.DataFrame,
    windows: list[int],
    features: list[str],
    min_n: int,
    bootstrap_n: int,
    include_no_trade: bool,
) -> pd.DataFrame:
    rows = []
    for window in windows:
        outcome = f"dump_{window}"
        window_frame = frame
        if not include_no_trade:
            window_frame = frame[~frame[f"no_trade_{window}"]]
        for feature in features:
            if feature not in window_frame:
                continue
            data = window_frame[[feature, outcome]].dropna()
            if len(data) < min_n or data[outcome].nunique() < 2:
                continue
            y = data[outcome].astype(int).to_numpy()
            x = data[feature].astype(float).to_numpy()
            auc, low, high = bootstrap_auc(y, x, n=bootstrap_n)
            flagged_n, flagged_rate, unflagged_rate, lift, precision = cohort_metrics(
                y, x
            )
            top_rate, _ = precision_at_top(y, x)
            base_rate = float(y.mean())
            rows.append(
                {
                    "window": window,
                    "feature": feature,
                    "n": len(data),
                    "base_rate": base_rate,
                    "auc": auc,
                    "ci_low": low,
                    "ci_high": high,
                    "flagged_n": flagged_n,
                    "flagged_rate": flagged_rate,
                    "unflagged_rate": unflagged_rate,
                    "lift": lift,
                    "precision": precision,
                    "top_rate": top_rate,
                    "top_lift": top_rate / base_rate if base_rate > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["window", "auc"], ascending=[True, False]
    )


def fmt(value, digits: int = 3) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{value:.{digits}f}"


def pct(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{value:.1%}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sprout.duckdb")
    parser.add_argument("--features", default="data/processed/launch_features.parquet")
    parser.add_argument("--windows", default=DEFAULT_WINDOWS)
    parser.add_argument("--drop", type=float, default=0.5)
    parser.add_argument("--since", default=None)
    parser.add_argument("--min-n", type=int, default=50)
    parser.add_argument("--bootstrap", type=int, default=300)
    parser.add_argument("--include-no-trade", action="store_true")
    parser.add_argument("--out", default="reports/short_horizon_dump.md")
    parser.add_argument(
        "--results-out", default="data/processed/short_horizon_results.parquet"
    )
    args = parser.parse_args()

    windows = parse_windows(args.windows)
    if not Path(args.db).exists():
        print(f"database missing: {args.db}; run load.py first", file=sys.stderr)
        return 2
    if not Path(args.features).exists():
        print(f"features missing: {args.features}; run signals.py first", file=sys.stderr)
        return 2

    features = pd.read_parquet(args.features)
    if args.since:
        since = pd.Timestamp(args.since, tz="UTC").timestamp()
        features = features[features["launch_time"] >= since].copy()
    features = features[
        features["price_60s"].notna()
        & (features["early_trades"].fillna(0) > 0)
        & (
            features["launch_time"] + 60 + max(windows)
            <= features["capture_max_time"]
        )
    ].copy()
    features = attach_dev_features(args.db, features, args.features)
    prices = load_short_prices(args.db, features, windows)
    frame = features.merge(prices, on="mint", how="left")
    frame = add_labels(frame, windows, args.drop)

    results = evaluate(
        frame,
        windows,
        CANDIDATE_FEATURES,
        args.min_n,
        args.bootstrap,
        args.include_no_trade,
    )
    if results.empty:
        print("no evaluable feature/window pairs", file=sys.stderr)
        return 2

    lines = [
        "# Short-horizon dump harness\n",
        "> **Exploratory; provisional data.** The capture predates the first-buy "
        "decoder fix; see [`KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md). This is not "
        "financial advice.\n",
        "## Method\n",
        f"- Label: minimum trade price in `(T+60s, T+60s+W]` is at or below "
        f"`price_60s * (1 - {args.drop:.0%})`.",
        "- `price_60s` is the last SOL/WSOL trade at or before T+60s.",
        "- A launch with no trade in the window is `no_trade` and is reported "
        "separately. By default it is excluded from the AUC because it has no "
        "observable dump path; `--include-no-trade` includes it as a non-dump.",
        "- Features are the launch-time features from `signals.py` plus the "
        "creator/dev features from `dev_dump.py`.",
        f"- Windows: {', '.join(f'{w}s' for w in windows)}; minimum n = {args.min_n}.",
        f"- AUC with {args.bootstrap}-sample bootstrap CIs; top decile at 10%.",
        "",
        "## Prevalence\n",
        "| Window | Launches | No trade | Traded | Dumps | Dump rate (traded) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for window in windows:
        outcome = f"dump_{window}"
        no_trade = frame[f"no_trade_{window}"]
        traded = frame[~no_trade]
        lines.append(
            f"| {window}s | {len(frame):,} | {int(no_trade.sum()):,} "
            f"| {len(traded):,} | {int(traded[outcome].sum()):,} "
            f"| {pct(traded[outcome].mean())} |"
        )
    lines.append("")

    lines.append("## Results by window\n")
    for window in windows:
        subset = results[results["window"] == window]
        lines.append(f"### {window}s\n")
        lines.append(
            "| Feature | n | Base | AUC | 95% CI | Top-decile dump | Top-decile lift |"
        )
        lines.append("|---|---:|---:|---:|---|---:|---:|")
        for _, row in subset.iterrows():
            lines.append(
                f"| {row['feature']} | {int(row['n']):,} | {pct(row['base_rate'])} "
                f"| {fmt(row['auc'])} | {fmt(row['ci_low'])}–{fmt(row['ci_high'])} "
                f"| {pct(row['top_rate'])} | {fmt(row['top_lift'], 2)}× |"
            )
        lines.append("")

    best = results.sort_values("auc", ascending=False).iloc[0]
    candidate = (
        best["auc"] >= 0.70
        and best["ci_low"] > 0.60
        and best["flagged_n"] >= 50
    )
    lines.append("## Verdict\n")
    if candidate:
        lines.append(
            f"`{best['feature']}` on the {int(best['window'])}s window reaches "
            f"AUC {fmt(best['auc'])} (95% CI {fmt(best['ci_low'])}–{fmt(best['ci_high'])}). "
            "That is a candidate for a fresh pre-registered capture, not a validated signal."
        )
    else:
        lines.append(
            f"No feature clears the exploratory bar (AUC ≥ 0.70, CI lower > 0.60, "
            f"n ≥ 50). Best: `{best['feature']}` at {int(best['window'])}s, "
            f"AUC {fmt(best['auc'])} (95% CI {fmt(best['ci_low'])}–{fmt(best['ci_high'])})."
        )
    lines.append("")
    lines.append(
        "This is an exploratory, multiple-testing-heavy harness on a pre-fix "
        "capture. It does not model execution, liquidity, or post-migration "
        "trades; a positive result would require a fresh pre-registered study."
    )

    report = Path(args.out)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines))
    results_out = Path(args.results_out)
    results_out.parent.mkdir(parents=True, exist_ok=True)
    results.to_parquet(results_out, index=False)

    print(f"wrote {report}")
    print(f"wrote {results_out}")
    print(
        f"best: {best['feature']} @ {int(best['window'])}s "
        f"AUC={fmt(best['auc'])} CI={fmt(best['ci_low'])}-{fmt(best['ci_high'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
