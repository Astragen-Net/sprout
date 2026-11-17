# Phase 0 findings — interim, 2026-11-14

> **Status: provisional.** The capture predates the first-buy decoder fix; see
> [`../../KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md). The stop/pivot decision is
> robust to the known issues, but the effect sizes are not final.

Data: 42,754 launches, 2.56M trades, 25.6 hours of pumpfun capture; 100% block-time coverage; zero balance-lookup decode errors (3.9M non-trade/unknown instructions ignored over the full capture). The v1 full-dataset rerun below uses the complete 122k-launch capture; the 42,754-launch snapshot was the interim.

**Time correction:** the measured slot rate is 4.649 slots/s (~215 ms/slot), not 400 ms. The original 150-slot "T+60s" window was ~32 s and the 216,000-slot "24h" horizon was ~13 h. All windows were moved to chain time (`blocks_meta`); the 12 h horizon is the best-powered interim, while the 24 h primary was underpowered in the early snapshot. The full captured dataset provides n=7,896 for the 24 h result.

## Primary hypothesis — FAILED, and inverted

`bundle_score` (share of early tokens bought by wallets in slots with ≥4 distinct buyers) does not predict rugs; higher scores are associated with **fewer** rugs.

| Horizon | n (confirmation) | Flagged n | Base rug | AUC | 95% CI | Flagged rug | Unflagged rug | Lift |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| 12 h | 2,170 | 191 | 17.0% | 0.452 | 0.444–0.461 | 1.6% | 18.4% | 0.09× |
| 24 h (full dataset) | 7,896 | 681 | 20.7% | 0.450 | 0.446–0.455 | 1.9% | 22.5% | 0.08× |
| 24 h (early snapshot) | 203 | — | — | 0.409 | 0.378–0.438 | — | — | underpowered |

The inversion is consistent across 1 h/6 h/12 h/24 h outcomes, terminal-price vs minimum-price, and the 3-buyer variant. It is not a time-window artifact. The generated full-dataset v1 report is [`phase0_v1_full_24h.md`](phase0_v1_full_24h.md).

**Why:** flagged launches are high-demand launches. Flagged vs unflagged early buyers: **12.5 vs 2.1**; early volume **11.1 vs 1.8 SOL**; trade-derived concentration **0.75 vs 0.37**. The same-slot flag measures demand, not coordination. Demand and liquidity reduce the chance of a 90% drawdown within 12 hours.

Baselines tell the same story: `early_buyers` AUC 0.359, `sniper_score` 0.356, `concentration_top10` 0.404 — all inverted. `early_buy_volume_sol` 0.593 and `creator_prior_launches` 0.593 are weakly positive.

## The one positive signal — insider network

`insider_score` is the share of early tokens bought by wallets that also bought in an earlier launch by the same creator. On the 12 h confirmation split:

- AUC **0.670** (95% CI 0.624–0.717), n = 793, decile lift **2.37×**, BH-adjusted p = **0.006**.
- Rugged launches: mean insider share **0.915** (median 1.000); survivors: **0.732** (median 0.983).
- Logistic model fit on exploration, evaluated on confirmation: insider alone **0.670**; creator history + insider **0.686**; plus early buy volume **0.696**. Correlation between insider and creator history is 0.195, so it adds independent information.
- Within the insider-known subset, `creator_prior_launches` alone is **inverted** (AUC 0.434); the all-rows 0.593 is a selection/Simpson effect. The repeat-buyer network, not raw launch count, carries the signal.

This is exploratory: a secondary hypothesis tested in the same capture, 12 h horizon, only 32% of launches have a known creator history (creators with ≤50 prior launches), and the 24 h out-of-sample confirmation is still pending.

## Interpretation

The original "bundle detection" wedge is not supported. The identity-graph thesis survives in a narrower form: **creator/insider network risk** — the recurring wallet network that buys a creator's successive launches. That is a different signal, a different buyer story, and a different product claim.

## Next validation (recommended)

1. Let the 72 h capture finish. Use the **remaining period** (after the current 25.6 h) as a clean out-of-sample window.
2. Pre-register a v2 hypothesis before evaluating it: `insider_score` at T+60s predicts 24 h rug, AUC ≥ 0.65 with CI lower bound > 0.55, decile lift ≥ 1.5×, on ≥200 known-creator launches in the fresh window.
3. Sharpen the score: repeat-buyer count across the creator's prior launches, prior creator rug rate, a cap-free treatment of high-volume creators, and a funding-link subsample if an RPC key is available.
4. Test the buyer pitch on this signal — serial-creator/insider-network risk — rather than generic bundle detection.
5. Do not start the rewrite. The bundle product is dead; the insider product is unconfirmed.

## Final v2 result — FAIL (2026-11-16)

Fresh window 2026-11-15 00:00 to 22:08; 23,709 fresh uncensored launches; 11,721 dead (no post-T+60s trade); 11,988 observed 24h outcomes; 5,624 known-creator launches before dead exclusion, 3,083 with observed outcomes. Primary n = 3,025:

- AUC **0.649** (95% CI 0.628–0.671) — below the 0.65 bar.
- High-insider cohort (≥0.9): 2,151 launches, rug rate **24.4%** vs **7.1%** rest, lift **3.44×**.
- Precision multiple **1.26×** — below the 1.30 bar.
- Secondary: expanded 0.607, repeat-≥2 0.618, creator history 0.601; bundle negative control 0.448 (inverted).
- The interim pass (0.653 AUC, 1.31× precision) did not hold on the full window.

The signal is weak-to-moderate and broad: the high cohort covers 71% of known-creator launches, and its rug rate is only 26% above base. It is not a standalone product.

**Data-quality caveat (2026-11-17):** the capture predates the first-buy decoder fix; ~24,914 launches have a first buy recorded as the curve remainder. Excluding the provably corrupt launches leaves the v2 AUC at ~0.646, below the bar, so the failure is robust; but the effect sizes are provisional. The 24h cohort also excludes 27,950 dead launches (no post-T+60s trade). See [`../../KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md).

## Dev-dump exploratory (2026-11-16)

The [`pumpfunbots-reverse`](https://github.com/zostaff/pumpfunbots-reverse) pattern (creator dev-buy, creator sell within 5s, prior creator dump rate, sell-only network) was tested on the existing 122k launches against 24h rug. The test is exploratory and uses the same pre-fix capture; treat the AUCs as provisional. It is **not supported at this horizon**; most features are inverted:

| Feature | n | AUC | 95% CI |
|---|---:|---:|---|
| creator_create_buy_share | 2,782 | 0.286 | 0.211–0.365 |
| creator_sold_5s | 26,333 | 0.448 | 0.445–0.450 |
| creator_prior_dump_rate | 21,125 | 0.443 | 0.440–0.445 |
| sell_only_network_share | 26,333 | 0.499 | 0.498–0.500 |
| insider_score (v2 comparator) | 6,716 | 0.657 | 0.642–0.671 |

Direct creator buying and selling, and prior dump history, predict **survival**, not a 24h rug. The repo's pattern may be a 5-second dump phenomenon that the 24h/90%-drawdown label does not capture, and dev-buys paid by sub-wallets are invisible in this measurement. No dev-dump feature met the AUC ≥ 0.70 exploratory bar. No rewrite.

## Decision rule status

- Original H1 (bundle): **fail, inverted**.
- V2 insider: **fail** the pre-registered bar (AUC 0.649 vs 0.65; precision 1.26 vs 1.30).
- Dev-dump exploratory: **not supported** at 24h; features inverted; no AUC ≥0.70.
- Buyer gate: not started.
- Rewrite: **not justified**.
- Recommended action: stop the product effort or pivot to sybil/airdrop clustering or custom indexer consulting. Do not lower the bar or start the rewrite.
- Data-quality status: provisional; see [`../../KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md). The stop decision is unchanged.
