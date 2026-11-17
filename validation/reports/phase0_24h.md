# Phase 0 report — pumpfun launch signals (24h outcome)

> **Historical intermediate report.** Produced with the pre-fix decoder and an
> earlier, underpowered capture snapshot; superseded by
> [`phase0_summary.md`](phase0_summary.md) and
> [`phase0_v2.md`](phase0_v2.md). See
> [`../../KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md).

- Launches captured: **42,754**
- Eligible for 24h outcomes: **1,271**
- Exploration / confirmation: **889 / 382**
- 24h rug prevalence: **16.2%**
- Median early trades: **24**
- Median early buyers: **1**

## Primary hypothesis: bundle_score → 24h rug

**Amendment 1:** flagged = `bundle_score > 0`, unflagged = `bundle_score == 0`. The decile table is context only because ~94% of scores are zero.

| Period | n | Flagged n | Base rate | AUC | 95% CI | Flagged rug | Unflagged rug | Lift | Precision multiple |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Exploration | 388 | 25 | 16.8% | 0.461 | 0.447–0.476 | 0.0% | 17.9% | 0.00× | 0.00× |
| Confirmation | 203 | 31 | 15.8% | 0.409 | 0.378–0.438 | 0.0% | 18.6% | 0.00× | 0.00× |

**Pre-registered bar (Amendment 1):** AUC ≥ 0.7, CI lower bound > 0.6, flagged vs unflagged lift ≥ 1.5×, precision multiple ≥ 1.3× base rate, n ≥ 500, flagged n ≥ 200. **Result: FAIL** (underpowered)

### Confirmation deciles (context only)

| Decile | n | Mean bundle score | Observed rug rate |
|---:|---:|---:|---:|
| 1 | 21 | 0.000 | 28.6% |
| 2 | 20 | 0.000 | 15.0% |
| 3 | 20 | 0.000 | 20.0% |
| 4 | 20 | 0.000 | 20.0% |
| 5 | 21 | 0.000 | 19.0% |
| 6 | 20 | 0.000 | 35.0% |
| 7 | 20 | 0.000 | 5.0% |
| 8 | 20 | 0.000 | 15.0% |
| 9 | 20 | 0.170 | 0.0% |
| 10 | 21 | 0.921 | 0.0% |

## Baselines on confirmation

| Feature | n | AUC | 95% CI | Decile lift |
|---|---:|---:|---|---:|
| early_buyers | 203 | 0.256 | 0.195–0.322 | 0.00× |
| early_volume_sol | 206 | 0.419 | 0.326–0.514 | 0.00× |
| early_buy_volume_sol | 203 | 0.480 | 0.376–0.579 | 0.00× |
| concentration_top10 | 203 | 0.496 | 0.417–0.574 | n/a× |
| creator_prior_launches | 206 | 0.702 | 0.620–0.779 | n/a× |

## Secondary hypotheses (confirmation)

| Signal | n | AUC | 95% CI | Decile lift | Perm p | BH-adjusted p |
|---|---:|---:|---|---:|---:|---:|
| sniper_score | 203 | 0.323 | 0.254–0.396 | 0.00× | 0.998 | 0.998 |
| concentration_top10 | 203 | 0.496 | 0.417–0.574 | n/a× | 0.579 | 0.868 |
| insider_score | 67 | 0.742 | 0.636–0.837 | n/a× | 0.004 | 0.012 |

Secondary success bar: AUC ≥ 0.65 and CI lower bound > 0.55, considered after Holm-BH correction.

## Sensitivity checks (confirmation)

| Variant | n | AUC | 95% CI | Decile lift |
|---|---:|---:|---|---:|
| bundle_score → rug_1h | 200 | 0.408 | 0.376–0.435 | 0.00× |
| bundle_score → rug_6h | 203 | 0.409 | 0.378–0.438 | 0.00× |
| bundle_score → rug_12h | 203 | 0.409 | 0.378–0.438 | 0.00× |
| bundle_score → rug_24h | 203 | 0.409 | 0.378–0.438 | 0.00× |
| bundle_score → terminal rug 24h | 203 | 0.412 | 0.382–0.440 | 0.00× |
| 3-buyer bundle → rug 24h | 203 | 0.365 | 0.332–0.401 | 0.00× |

## Limitations

- No RPC funding graph in v0; bundle detection is same-slot co-buying.
- Concentration is trade-derived; transfers, burns and closed accounts are invisible.
- Post-migration AMM trades are not captured; migrated-token outcomes are stale.
- Creator history is constrained by the 72h capture; insider is exploratory.
- One venue and SOL-quoted coins only; USDC/other quote mints are excluded.
- Price-based rug definition only; no liquidity-pull data.
