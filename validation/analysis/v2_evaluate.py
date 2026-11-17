#!/usr/bin/env python3
"""Evaluate the pre-registered v2 insider-network hypothesis on the fresh window.

Run only after the capture has produced 24h outcomes for the fresh window
(>= 2026-11-15T00:00:00Z). No threshold is tuned here; the bars come from
PREREGISTRATION_V2.md.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import bh_adjust, bootstrap_auc, permutation_p  # noqa: E402

SINCE = "2026-11-15T00:00:00Z"
OUTCOME = "rug_24h"
HIGH_THRESHOLD = 0.9
MIN_KNOWN = 200


def eval_signal(frame: pd.DataFrame, signal: str, outcome: str, mask=None):
    data = frame if mask is None else frame[mask]
    data = data[[signal, outcome]].dropna()
    if len(data) < 20 or data[outcome].nunique() < 2:
        return {"n": len(data), "auc": np.nan, "ci_low": np.nan, "ci_high": np.nan, "y": None, "x": None}
    y = data[outcome].astype(int).to_numpy()
    x = data[signal].astype(float).to_numpy()
    auc, low, high = bootstrap_auc(y, x)
    return {"n": len(data), "auc": auc, "ci_low": low, "ci_high": high, "y": y, "x": x}


def high_cohort(y: np.ndarray, x: np.ndarray, threshold: float = HIGH_THRESHOLD):
    high = x >= threshold
    if not high.any() or not (~high).any():
        return 0, np.nan, np.nan, np.nan, np.nan
    high_rate = float(y[high].mean())
    rest_rate = float(y[~high].mean())
    base = float(y.mean())
    lift = high_rate / rest_rate if rest_rate > 0 else np.nan
    precision = high_rate / base if base > 0 else np.nan
    return int(high.sum()), high_rate, rest_rate, lift, precision


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
    parser.add_argument("--features", default="data/processed/launch_features.parquet")
    parser.add_argument("--since", default=SINCE)
    parser.add_argument("--out", default="reports/phase0_v2.md")
    args = parser.parse_args()

    frame = pd.read_parquet(args.features)
    since = pd.Timestamp(args.since, tz="UTC").timestamp()
    cohort = frame[
        (frame["launch_time"] >= since)
        & (~frame["censored_24h"].fillna(True))
        & frame["price_60s"].notna()
        & (frame["early_trades"].fillna(0) > 0)
    ].copy()
    dead = int(cohort[OUTCOME].isna().sum())
    fresh = cohort[cohort[OUTCOME].notna()].copy()
    known = fresh["insider_known"].fillna(False).astype(bool)

    primary = eval_signal(fresh, "insider_score", OUTCOME, known)
    high_n, high_rate, rest_rate, lift, precision = (
        high_cohort(primary["y"], primary["x"]) if primary["y"] is not None
        else (0, np.nan, np.nan, np.nan, np.nan)
    )
    passed = (
        primary["n"] >= MIN_KNOWN
        and primary["auc"] >= 0.65
        and primary["ci_low"] > 0.55
        and lift >= 1.5
        and precision >= 1.3
    )

    secondary_specs = [
        ("insider_score_expanded", "insider_known_expanded", "insider_score_expanded"),
        ("insider_score_2plus", "insider_known_expanded", "insider_score_2plus"),
        ("creator_prior_launches", None, "creator_prior_launches"),
        ("bundle_score (negative control)", None, "bundle_score"),
    ]
    secondary_rows = []
    for label, known_col, column in secondary_specs:
        mask = None
        if known_col is not None:
            mask = fresh[known_col].fillna(False).astype(bool) if known_col in fresh else None
        result = eval_signal(fresh, column, OUTCOME, mask)
        p_value = np.nan
        if result["y"] is not None:
            p_value = permutation_p(result["y"], result["x"])
        secondary_rows.append((label, result, p_value))
    adjusted = bh_adjust([row[2] for row in secondary_rows])

    v1 = frame[(frame["launch_time"] < since)]
    train = v1[
        v1["insider_known"].fillna(False).astype(bool)
        & v1[OUTCOME].notna()
        & (~v1["censored_24h"].fillna(True))
    ]
    test = fresh[known]
    feature_columns = ["creator_prior_launches", "insider_score", "early_buy_volume_sol"]
    combined_auc = np.nan
    combined_n = 0
    if len(train) >= 50 and len(test) >= 50:
        model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
        train_data = train[feature_columns + [OUTCOME]].dropna()
        test_data = test[feature_columns + [OUTCOME]].dropna()
        if len(train_data) >= 50 and len(test_data) >= 50 and test_data[OUTCOME].nunique() > 1:
            model.fit(train_data[feature_columns], train_data[OUTCOME].astype(int))
            probabilities = model.predict_proba(test_data[feature_columns])[:, 1]
            combined_auc = roc_auc_score(test_data[OUTCOME].astype(int), probabilities)
            combined_n = len(test_data)

    lines: list[str] = []
    lines.append("# Phase 0 v2 — insider-network validation\n")
    lines.append(
        "**Data status:** the capture used for these results predates the first-buy "
        "decoder fix; see `KNOWN_ISSUES.md`. Effect sizes are provisional.\n"
    )
    lines.append(f"- Fresh window start: `{args.since}`")
    lines.append(
        f"- Fresh uncensored cohort (T+60s price, early trades): **{len(cohort):,}**"
    )
    lines.append(f"- Dead (no post-T+60s trade): **{dead:,}**")
    lines.append(f"- Fresh launches with observed 24h outcomes: **{len(fresh):,}**")
    lines.append(f"- Known-creator launches with observed outcomes: **{int(known.sum()):,}**")
    if len(fresh):
        lines.append(
            f"- 24h rug prevalence among observed fresh launches: "
            f"**{fresh[OUTCOME].mean():.1%}**"
        )
    lines.append("")

    lines.append("## Primary: insider_score → 24h rug\n")
    lines.append("| n known | AUC | 95% CI | High cohort (≥0.9) n | High rug | Rest rug | Lift | Precision multiple |")
    lines.append("|---:|---:|---|---:|---:|---:|---:|---:|")
    lines.append(
        f"| {primary['n']:,} | {fmt(primary['auc'])} "
        f"| {fmt(primary['ci_low'])}–{fmt(primary['ci_high'])} "
        f"| {high_n:,} | {pct(high_rate)} | {pct(rest_rate)} "
        f"| {fmt(lift, 2)}× | {fmt(precision, 2)}× |"
    )
    lines.append("")
    lines.append(
        f"**Pre-registered bar:** AUC ≥ 0.65, CI lower > 0.55, high-cohort lift ≥ 1.5×, "
        f"precision ≥ 1.3× base rate, n ≥ {MIN_KNOWN}. "
        f"**Result: {'PASS' if passed else 'FAIL'}**"
    )
    lines.append("")

    lines.append("## Secondary signals\n")
    lines.append("| Signal | n | AUC | 95% CI | Perm p | BH-adjusted p |")
    lines.append("|---|---:|---:|---|---:|---:|")
    for (signal, result, p_value), adjusted_p in zip(secondary_rows, adjusted):
        lines.append(
            f"| {signal} | {result['n']:,} | {fmt(result['auc'])} "
            f"| {fmt(result['ci_low'])}–{fmt(result['ci_high'])} "
            f"| {fmt(p_value)} | {fmt(adjusted_p)} |"
        )
    lines.append("")

    lines.append("## Combined model (fit on v1, evaluated on fresh)\n")
    lines.append(
        f"- Features: {', '.join(feature_columns)}"
        f"\n- Train n: {len(train):,}; test n: {combined_n:,}"
        f"\n- AUC: **{fmt(combined_auc)}**"
    )
    lines.append("")

    lines.append("## Limitations\n")
    lines.append("- Pumpfun and SOL-quoted coins only; price-based rug definition.")
    lines.append("- No funding-graph tracing; insider is a repeat-buyer proxy.")
    lines.append("- Coverage depends on prior launches; the 24h window limits the fresh sample.")
    lines.append(
        "- Dead launches (no post-T+60s trade) are reported separately and excluded "
        "from the price-based rug AUC."
    )
    lines.append(
        "- Captures made before the first-buy fix may misstate early buy amounts; "
        "see `KNOWN_ISSUES.md`."
    )
    lines.append("- Do not tune thresholds on this window; a secondary pass without the primary is not confirmation.\n")

    report = Path(args.out)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines))
    print(f"wrote {report}")
    print(
        f"primary: n={primary['n']:,} auc={fmt(primary['auc'])} "
        f"ci={fmt(primary['ci_low'])}-{fmt(primary['ci_high'])} "
        f"high_n={high_n:,} lift={fmt(lift, 2)} precision={fmt(precision, 2)} "
        f"{'PASS' if passed else 'FAIL'}"
    )
    print(f"combined model AUC: {fmt(combined_auc)} (test n={combined_n:,})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
