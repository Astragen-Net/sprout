#!/usr/bin/env python3
"""Evaluate the pre-registered Phase 0 hypotheses.

Primary: bundle_score at T+60s predicts a 24h rug on the held-out confirmation
period. Secondary signals are corrected with Holm-BH. Writes a Markdown report
and two charts under reports/.
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, roc_curve

PRIMARY_SIGNAL = "bundle_score"
SECONDARY_SIGNALS = ["sniper_score", "concentration_top10", "insider_score"]
BASELINES = [
    "early_buyers",
    "early_volume_sol",
    "early_buy_volume_sol",
    "concentration_top10",
    "creator_prior_launches",
]
MIN_CONFIRMATION_SAMPLE = 500
MIN_FLAGGED_SAMPLE = 200


def bootstrap_auc(y: np.ndarray, x: np.ndarray, n: int = 1000, seed: int = 42):
    if len(np.unique(y)) < 2:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    observed = roc_auc_score(y, x)
    values = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        sample = y[idx]
        if sample.min() == sample.max():
            continue
        values.append(roc_auc_score(sample, x[idx]))
    if not values:
        return observed, np.nan, np.nan
    low, high = np.percentile(values, [2.5, 97.5])
    return observed, low, high


def decile_table(y: np.ndarray, x: np.ndarray, bins: int = 10) -> pd.DataFrame:
    frame = pd.DataFrame({"y": y, "x": x})
    frame["decile"] = pd.qcut(frame["x"].rank(method="first"), bins, labels=False)
    table = frame.groupby("decile").agg(
        n=("y", "size"),
        rug_rate=("y", "mean"),
        mean_signal=("x", "mean"),
    )
    table.index = table.index + 1
    return table


def precision_at_top(y: np.ndarray, x: np.ndarray, fraction: float = 0.1):
    threshold = np.quantile(x, 1 - fraction)
    mask = x >= threshold
    return float(y[mask].mean()) if mask.any() else np.nan, float(mask.mean())


def permutation_p(y: np.ndarray, x: np.ndarray, n: int = 500, seed: int = 42) -> float:
    observed = roc_auc_score(y, x)
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n):
        permuted = rng.permutation(y)
        if roc_auc_score(permuted, x) >= observed:
            count += 1
    return (count + 1) / (n + 1)


def bh_adjust(p_values: list[float]) -> list[float]:
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    if n == 0:
        return []
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output = np.empty(n)
    output[order] = np.clip(adjusted, 0, 1)
    return output.tolist()


def cohort_metrics(y: np.ndarray, x: np.ndarray):
    y = np.asarray(y)
    x = np.asarray(x)
    flagged = x > 0
    unflagged = ~flagged
    flagged_n = int(flagged.sum())
    flagged_rate = float(y[flagged].mean()) if flagged_n else np.nan
    unflagged_rate = float(y[unflagged].mean()) if unflagged.any() else np.nan
    if unflagged_rate and not np.isnan(unflagged_rate) and unflagged_rate > 0:
        lift = flagged_rate / unflagged_rate
    else:
        lift = np.nan
    base = float(y.mean())
    precision_multiple = flagged_rate / base if base > 0 else np.nan
    return flagged_n, flagged_rate, unflagged_rate, lift, precision_multiple


def evaluate_signal(frame: pd.DataFrame, signal: str, outcome: str, subset_mask=None) -> dict:
    data = frame
    if subset_mask is not None:
        data = data[subset_mask]
    data = data[[signal, outcome]].dropna()
    if data.empty or len(np.unique(data[outcome])) < 2:
        return {"n": len(data), "auc": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    y = data[outcome].astype(int).to_numpy()
    x = data[signal].astype(float).to_numpy()
    auc, low, high = bootstrap_auc(y, x)
    table = decile_table(y, x)
    top_rate = float(table["rug_rate"].iloc[-1])
    bottom_rate = float(table["rug_rate"].iloc[0])
    lift = top_rate / bottom_rate if bottom_rate > 0 else np.nan
    top_precision, top_fraction = precision_at_top(y, x)
    return {
        "n": len(data),
        "base_rate": float(y.mean()),
        "auc": auc,
        "ci_low": low,
        "ci_high": high,
        "top_decile_rate": top_rate,
        "bottom_decile_rate": bottom_rate,
        "decile_lift": lift,
        "top_precision": top_precision,
        "top_fraction": top_fraction,
        "deciles": table,
        "y": y,
        "x": x,
    }


def format_metric(value, digits=3):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{value:.{digits}f}"


def format_pct(value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    return f"{value:.1%}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default="data/processed/launch_features.parquet")
    parser.add_argument("--out", default="reports/phase0_report.md")
    parser.add_argument("--charts", default="reports")
    parser.add_argument("--horizon", default="24h", choices=["1h", "6h", "12h", "24h"])
    args = parser.parse_args()

    horizon = args.horizon
    outcome = f"rug_{horizon}"
    censored = f"censored_{horizon}"

    frame = pd.read_parquet(args.features)
    frame = frame.sort_values("slot").reset_index(drop=True)
    eligible = frame[
        (~frame[censored].fillna(True))
        & frame["price_60s"].notna()
        & (frame["early_trades"].fillna(0) > 0)
    ].copy()

    cut = int(len(eligible) * 0.7)
    exploration = eligible.iloc[:cut]
    confirmation = eligible.iloc[cut:]

    lines: list[str] = []
    lines.append(f"# Phase 0 report — pumpfun launch signals ({horizon} outcome)\n")
    if horizon != "24h":
        lines.append(
            f"**Interim horizon: {horizon}. The pre-registered primary outcome is 24h; "
            "this report is descriptive until the 24h sample matures.**\n"
        )
    lines.append(f"- Launches captured: **{len(frame):,}**")
    lines.append(f"- Eligible for {horizon} outcomes: **{len(eligible):,}**")
    lines.append(f"- Exploration / confirmation: **{len(exploration):,} / {len(confirmation):,}**")
    if len(eligible):
        lines.append(f"- {horizon} rug prevalence: **{eligible[outcome].mean():.1%}**")
        lines.append(f"- Median early trades: **{eligible['early_trades'].median():.0f}**")
        lines.append(f"- Median early buyers: **{eligible['early_buyers'].median():.0f}**")
    lines.append("")

    primary_explore = evaluate_signal(exploration, PRIMARY_SIGNAL, outcome)
    primary_confirm = evaluate_signal(confirmation, PRIMARY_SIGNAL, outcome)

    bar = {"auc": 0.70, "ci_low": 0.60, "lift": 1.5, "precision_multiple": 1.3}
    n_confirm = primary_confirm.get("n", 0)
    if "y" in primary_confirm:
        flagged_n, flagged_rate, unflagged_rate, lift, precision_multiple = cohort_metrics(
            primary_confirm["y"], primary_confirm["x"]
        )
    else:
        flagged_n, flagged_rate, unflagged_rate, lift, precision_multiple = 0, np.nan, np.nan, np.nan, np.nan
    passed = (
        n_confirm >= MIN_CONFIRMATION_SAMPLE
        and flagged_n >= MIN_FLAGGED_SAMPLE
        and primary_confirm.get("auc", 0) >= bar["auc"]
        and primary_confirm.get("ci_low", 0) > bar["ci_low"]
        and lift >= bar["lift"]
        and precision_multiple >= bar["precision_multiple"]
    )

    lines.append(f"## Primary hypothesis: bundle_score → {horizon} rug\n")
    lines.append(
        "**Amendment 1:** flagged = `bundle_score > 0`, unflagged = `bundle_score == 0`. "
        "The decile table is context only because ~94% of scores are zero.\n"
    )
    lines.append(
        "| Period | n | Flagged n | Base rate | AUC | 95% CI | Flagged rug | Unflagged rug | Lift | Precision multiple |"
    )
    lines.append("|---|---:|---:|---:|---:|---|---:|---:|---:|---:|")
    for name, result in (("Exploration", primary_explore), ("Confirmation", primary_confirm)):
        if "y" in result:
            f_n, f_rate, u_rate, f_lift, f_precision = cohort_metrics(result["y"], result["x"])
        else:
            f_n, f_rate, u_rate, f_lift, f_precision = 0, np.nan, np.nan, np.nan, np.nan
        lines.append(
            f"| {name} | {result.get('n', 0):,} | {f_n:,} | {format_pct(result.get('base_rate'))} "
            f"| {format_metric(result.get('auc'))} "
            f"| {format_metric(result.get('ci_low'))}–{format_metric(result.get('ci_high'))} "
            f"| {format_pct(f_rate)} | {format_pct(u_rate)} "
            f"| {format_metric(f_lift, 2)}× | {format_metric(f_precision, 2)}× |"
        )
    lines.append("")
    lines.append(
        f"**Pre-registered bar (Amendment 1):** AUC ≥ {bar['auc']}, CI lower bound > {bar['ci_low']}, "
        f"flagged vs unflagged lift ≥ {bar['lift']}×, precision multiple ≥ {bar['precision_multiple']}× "
        f"base rate, n ≥ {MIN_CONFIRMATION_SAMPLE:,}, flagged n ≥ {MIN_FLAGGED_SAMPLE:,}. "
        f"**Result: {'PASS' if passed else 'FAIL'}**"
        + ("" if n_confirm >= MIN_CONFIRMATION_SAMPLE else " (underpowered)")
    )
    lines.append("")

    if "deciles" in primary_confirm:
        lines.append("### Confirmation deciles (context only)\n")
        lines.append("| Decile | n | Mean bundle score | Observed rug rate |")
        lines.append("|---:|---:|---:|---:|")
        for decile, row in primary_confirm["deciles"].iterrows():
            lines.append(
                f"| {decile} | {int(row['n']):,} | {row['mean_signal']:.3f} | {row['rug_rate']:.1%} |"
            )
        lines.append("")

    lines.append("## Baselines on confirmation\n")
    lines.append("| Feature | n | AUC | 95% CI | Decile lift |")
    lines.append("|---|---:|---:|---|---:|")
    for signal in BASELINES:
        result = evaluate_signal(confirmation, signal, outcome)
        lines.append(
            f"| {signal} | {result.get('n', 0):,} | {format_metric(result.get('auc'))} "
            f"| {format_metric(result.get('ci_low'))}–{format_metric(result.get('ci_high'))} "
            f"| {format_metric(result.get('decile_lift'), 2)}× |"
        )
    lines.append("")

    lines.append("## Secondary hypotheses (confirmation)\n")
    lines.append("| Signal | n | AUC | 95% CI | Decile lift | Perm p | BH-adjusted p |")
    lines.append("|---|---:|---:|---|---:|---:|---:|")
    secondary_rows = []
    for signal in SECONDARY_SIGNALS:
        subset = None
        if signal == "insider_score":
            subset = confirmation["insider_known"].fillna(False).astype(bool)
        result = evaluate_signal(confirmation, signal, outcome, subset)
        p_value = np.nan
        if result.get("n", 0) > 0 and not np.isnan(result.get("auc", np.nan)):
            data = confirmation if subset is None else confirmation[subset]
            data = data[[signal, outcome]].dropna()
            if len(np.unique(data[outcome])) > 1:
                p_value = permutation_p(
                    data[outcome].astype(int).to_numpy(),
                    data[signal].astype(float).to_numpy(),
                )
        secondary_rows.append((signal, result, p_value))
    adjusted = bh_adjust([row[2] for row in secondary_rows])
    for (signal, result, p_value), adjusted_p in zip(secondary_rows, adjusted):
        lines.append(
            f"| {signal} | {result.get('n', 0):,} | {format_metric(result.get('auc'))} "
            f"| {format_metric(result.get('ci_low'))}–{format_metric(result.get('ci_high'))} "
            f"| {format_metric(result.get('decile_lift'), 2)}× "
            f"| {format_metric(p_value)} | {format_metric(adjusted_p)} |"
        )
    lines.append("")
    lines.append(
        "Secondary success bar: AUC ≥ 0.65 and CI lower bound > 0.55, "
        "considered after Holm-BH correction.\n"
    )

    lines.append("## Sensitivity checks (confirmation)\n")
    lines.append("| Variant | n | AUC | 95% CI | Decile lift |")
    lines.append("|---|---:|---:|---|---:|")
    sensitivity = [
        ("bundle_score → rug_1h", "bundle_score", "rug_1h"),
        ("bundle_score → rug_6h", "bundle_score", "rug_6h"),
        ("bundle_score → rug_12h", "bundle_score", "rug_12h"),
        ("bundle_score → rug_24h", "bundle_score", "rug_24h"),
        ("bundle_score → terminal rug 24h", "bundle_score", "terminal_rug_24h"),
        ("3-buyer bundle → rug 24h", "bundle_score_3", "rug_24h"),
    ]
    for label, signal, outcome in sensitivity:
        result = evaluate_signal(confirmation, signal, outcome)
        lines.append(
            f"| {label} | {result.get('n', 0):,} | {format_metric(result.get('auc'))} "
            f"| {format_metric(result.get('ci_low'))}–{format_metric(result.get('ci_high'))} "
            f"| {format_metric(result.get('decile_lift'), 2)}× |"
        )
    lines.append("")

    lines.append("## Limitations\n")
    lines.append("- No RPC funding graph in v0; bundle detection is same-slot co-buying.")
    lines.append("- Concentration is trade-derived; transfers, burns and closed accounts are invisible.")
    lines.append("- Post-migration AMM trades are not captured; migrated-token outcomes are stale.")
    lines.append("- Creator history is constrained by the 72h capture; insider is exploratory.")
    lines.append("- One venue and SOL-quoted coins only; USDC/other quote mints are excluded.")
    lines.append("- Price-based rug definition only; no liquidity-pull data.\n")

    report_path = Path(args.out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines))
    print(f"wrote {report_path}")

    charts = Path(args.charts)
    charts.mkdir(parents=True, exist_ok=True)
    if "deciles" in primary_confirm:
        table = primary_confirm["deciles"]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(table.index.astype(str), table["rug_rate"] * 100, color="#4c72b0")
        ax.set_xlabel("bundle_score decile")
        ax.set_ylabel("24h rug rate (%)")
        ax.set_title("Confirmation: rug rate by bundle score decile")
        fig.tight_layout()
        fig.savefig(charts / "decile_lift.png", dpi=150)
        plt.close(fig)
    if "y" in primary_confirm:
        fpr, tpr, _ = roc_curve(primary_confirm["y"], primary_confirm["x"])
        fig, ax = plt.subplots(figsize=(5, 5))
        ax.plot(fpr, tpr, label=f"AUC {primary_confirm['auc']:.3f}")
        ax.plot([0, 1], [0, 1], linestyle="--", color="grey")
        ax.set_xlabel("False positive rate")
        ax.set_ylabel("True positive rate")
        ax.set_title("Confirmation ROC: bundle_score")
        ax.legend()
        fig.tight_layout()
        fig.savefig(charts / "roc_bundle.png", dpi=150)
        plt.close(fig)

    print(
        f"primary: n={n_confirm:,} auc={format_metric(primary_confirm.get('auc'))} "
        f"ci={format_metric(primary_confirm.get('ci_low'))}-{format_metric(primary_confirm.get('ci_high'))} "
        f"lift={format_metric(primary_confirm.get('decile_lift'), 2)} "
        f"precision_multiple={format_metric(precision_multiple, 2)} "
        f"{'PASS' if passed else 'FAIL'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
