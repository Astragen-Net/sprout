# Findings: do pump.fun launch signals predict rugs?

> **Status: provisional.** The 72-hour capture predates the first-buy decoder fix; see [KNOWN_ISSUES.md](KNOWN_ISSUES.md). The stop/pivot decision is robust to the known issues, but the effect sizes below are not final.

## Data

- 72 hours of live Yellowstone gRPC capture: 2026-11-13 22:08 to 2026-11-16 22:08 UTC.
- 21,210,944 transactions, 122,660 launch events (122,121 unique mints), 7,552,052 trade events (7,524,596 after dedupe), 3,868 migrations, zero balance-lookup decode errors (3,923,051 non-trade/unknown pumpfun instructions were ignored).
- Pumpfun only; SOL/WSOL-quoted coins. Windows use **chain time** from `blocks_meta`, not ingest time. The measured slot rate is ~4.65 slots/s (~215 ms/slot).
- 24-hour cohort: 54,629 uncensored launches with a T+60s price and early trades; 27,950 (51.2%) had no post-T+60s trade (dead) and are excluded from price-based rug AUC; 26,679 observed 24h outcomes. Rug prevalence among observed launches: **19.1%**.

## Method

- Pre-registered v1 (`PREREGISTRATION.md`) and v2 (`PREREGISTRATION_V2.md`) before outcome analysis. v2 used a non-overlapping fresh window.
- Features computed at **T+60s** chain time.
- Primary outcome: **24h rug** = minimum price within 24 hours is at most 10% of the T+60s price. Price is the last SOL/WSOL trade price `quote/base`.
- Dead launches (no post-T+60s trade) are reported separately and excluded from rug AUC by construction.
- Metrics: AUC with 1,000-sample bootstrap CIs, decile lift, flagged-vs-unflagged rates, permutation p-values with Holm-BH correction.
- Negative control: `bundle_score` should not be positively predictive; it is inverted.

## Results

### 1. Same-slot bundle score — failed, inverted

`bundle_score` = share of early bought tokens bought by wallets in slots with at least 4 distinct buyers (same-slot co-buying).

| Horizon | n | AUC | 95% CI | Flagged rug | Unflagged rug |
|---|---:|---:|---|---:|---:|
| 12 h (v1 interim) | 2,170 | 0.452 | 0.444–0.461 | 1.6% | 18.4% |
| 24 h (full captured dataset) | 7,896 | 0.450 | 0.446–0.455 | 1.9% | 22.5% |
| 24 h (early underpowered snapshot) | 203 | 0.409 | 0.378–0.438 | — | — |

The full 24 h result is consistent with the 12 h interim; the n=203 row was an early snapshot before the capture matured. The generated full-dataset report is [`validation/reports/phase0_v1_full_24h.md`](validation/reports/phase0_v1_full_24h.md). Flagged launches have 12.5 early buyers vs 2.1, 11.1 vs 1.8 SOL early volume, and 0.75 vs 0.37 trade-derived concentration. The flag measures **demand**, not coordination; demand and liquidity reduce the chance of a 90% drawdown.

### 2. Insider repeat-buyer network — real but below the bar

`insider_score` = share of early bought tokens bought by wallets that also bought an earlier launch by the same creator.

| Metric | v2 final |
|---|---:|
| n (known creator + valid 24h outcome) | 3,025 |
| AUC | **0.649** (95% CI 0.628–0.671) |
| High-insider cohort (≥0.9) | 2,151 launches |
| High cohort rug rate | 24.4% |
| Rest rug rate | 7.1% |
| Lift | 3.44× |
| Precision multiple | 1.26× |
| Pre-registered bar | AUC ≥ 0.65, CI low > 0.55, lift ≥ 1.5×, precision ≥ 1.3×, n ≥ 200 → **FAIL** |

The signal replicates directionally but is broad: 71% of known-creator launches fall in the high cohort, and its rug rate is only 26% above base. The interim pass (0.653 / 1.31×) did not hold on the full window.

### 3. Creator dev-buy / launch-and-dump — inverted at 24h

Inspired by the open-source [`pumpfunbots-reverse`](https://github.com/zostaff/pumpfunbots-reverse) research (creator dev-buys, fast sells, sell-only networks). Tested on the existing 122k-launch dataset as an exploratory check, not a pre-registered gate.

| Feature | n | AUC | 95% CI |
|---|---:|---:|---|
| creator_create_buy_share | 2,782 | 0.286 | 0.211–0.365 |
| creator_sold_5s | 26,333 | 0.448 | 0.445–0.450 |
| creator_prior_dump_rate | 21,125 | 0.443 | 0.440–0.445 |
| sell_only_network_share | 26,333 | 0.499 | 0.498–0.500 |
| insider_score (comparator) | 6,716 | 0.657 | 0.642–0.671 |

Direct creator buying/selling and prior dump history predict **survival**, not a 24h rug. Launches with a creator sell within 5 seconds rug at ~0.8% vs a 19.1% base rate. The repo's pattern may be a **5-second dump** that a 24h/90%-drawdown label does not capture; dev-buys paid by sub-wallets are also invisible in this measurement.

### 4. Replay backtest — no profit edge

An exploratory replay (`validation/analysis/replay_backtest.py`) enters at the first trade after T+60s, holds to 24h, and applies 1% fee + 1% slippage on each side. On the v2 fresh window:

| Cohort | Filled | Mean | Median | Win rate |
|---|---:|---:|---:|---:|
| insider_score ≥ 0.9 | 1,830 | -34.9% | -67.0% | 13.9% |
| insider_score < 0.9 | 738 | -30.2% | -33.7% | 10.4% |
| random | 1,962 | -35.0% | -58.5% | 12.8% |
| all | 2,568 | -33.6% | -57.0% | 12.9% |

The high-signal cohort is **worse** than the rest on median return, and every cohort loses money. Zero-cost, 50%-stop, and 1h-horizon variants remain negative. The mean is negative even before costs. This is not a tradable profit edge. See [`validation/reports/replay_backtest.md`](validation/reports/replay_backtest.md) for the full method, bootstrap intervals and caveats.

## Data quality

- The capture predates the first-buy decoder fix. ~24,914 launches have a first buy >500M tokens (the curve remainder), which inflates `early_buy_base` and dilutes the share features; 403/3,025 v2 primary launches are affected. Excluding them leaves the v2 AUC at ~0.646, so the failure is robust, but the effect sizes are provisional. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
- 27,950/54,629 (51.2%) of the 24h cohort have no post-T+60s trade and are excluded from rug AUC. The 19.1% prevalence is among the 26,679 observed launches, not the full cohort.
- `ignored=3,923,051`; `multi_hop_curve_swap` and `migrate_bonding_curve_creator` are not decoded. “Zero decode errors” refers to balance lookups only.

## Interpretation

- The launch-level "bundle detection" wedge is not supported. It is a demand/latency signal.
- These effect sizes are provisional: the capture predates the first-buy decoder fix and excludes dead launches from rug AUC. The stop decision is robust, but rerun on regenerated data before citing exact numbers.
- The identity-graph signal is real but weak and broad at the launch level. As a standalone product it fails the pre-registered bar.
- The dev-dump pattern from the open-source bot research does not transfer to 24h rug outcomes. Testing it properly would require a **5–60 second** dump label, sub-wallet/funding-link tracing, and a different buyer (pre-trade avoidance for bots).
- The honest conclusion: do not build the launch-identity API on this evidence. The capture and validation infrastructure remain reusable for a different question.

## Reproducibility

- Pre-registrations and success bars are frozen in `PREREGISTRATION.md` and `PREREGISTRATION_V2.md`.
- The capture tool and analysis scripts are in `validation/`; a one-minute fixture is in `validation/fixtures/`.
- The raw capture and full dataset are not included. The capture tool can reproduce them with a provider token.
- The published capture stores only decoded events; a decoder fix cannot be applied retroactively. Re-capture with the fixed decoder (or backfill the affected create transactions) before reproducing the numbers.

## Limitations

- Pumpfun and SOL/WSOL only; USDC/other quote mints excluded.
- Price-based rug definition; no liquidity-pull data.
- No funding-graph tracing; insider is a repeat-buyer proxy.
- Post-migration AMM trades are not captured; migrated-token outcomes are stale.
- Direct creator-wallet measurement misses dev-buys paid by sub-wallets.
- The 24h maturity window limited the v2 fresh sample to ~22 hours of launches.
- First-buy amounts in the published capture are misstated for create+buy launches; see `KNOWN_ISSUES.md`.
- Dead launches (no post-T+60s trade) are excluded from price-based rug AUC and reported separately.
- Coverage is not complete: 3.9M pumpfun instructions were ignored, including multi-hop swaps and one migration variant.
- The capture stores no raw transactions, so old captures cannot be re-decoded.
- Findings are observational and not financial advice.
