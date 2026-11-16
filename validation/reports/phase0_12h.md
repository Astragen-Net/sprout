# Phase 0 report — pumpfun launch signals (12h outcome)

**Interim horizon: 12h. The pre-registered primary outcome is 24h; this report is descriptive until the 24h sample matures.**

- Launches captured: **42,754**
- Eligible for 12h outcomes: **15,439**
- Exploration / confirmation: **10,807 / 4,632**
- 12h rug prevalence: **18.2%**
- Median early trades: **23**
- Median early buyers: **1**

## Primary hypothesis: bundle_score → 12h rug

**Amendment 1:** flagged = `bundle_score > 0`, unflagged = `bundle_score == 0`. The decile table is context only because ~94% of scores are zero.

| Period | n | Flagged n | Base rate | AUC | 95% CI | Flagged rug | Unflagged rug | Lift | Precision multiple |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Exploration | 5,080 | 499 | 18.9% | 0.440 | 0.435–0.445 | 0.2% | 21.0% | 0.01× | 0.01× |
| Confirmation | 2,170 | 191 | 17.0% | 0.452 | 0.444–0.461 | 1.6% | 18.4% | 0.09× | 0.09× |

**Pre-registered bar (Amendment 1):** AUC ≥ 0.7, CI lower bound > 0.6, flagged vs unflagged lift ≥ 1.5×, precision multiple ≥ 1.3× base rate, n ≥ 500, flagged n ≥ 200. **Result: FAIL**

### Confirmation deciles (context only)

| Decile | n | Mean bundle score | Observed rug rate |
|---:|---:|---:|---:|
| 1 | 217 | 0.000 | 16.6% |
| 2 | 217 | 0.000 | 18.4% |
| 3 | 217 | 0.000 | 17.5% |
| 4 | 217 | 0.000 | 21.7% |
| 5 | 217 | 0.000 | 17.1% |
| 6 | 217 | 0.000 | 18.9% |
| 7 | 217 | 0.000 | 16.6% |
| 8 | 217 | 0.000 | 19.8% |
| 9 | 217 | 0.000 | 18.4% |
| 10 | 217 | 0.533 | 4.6% |

## Baselines on confirmation

| Feature | n | AUC | 95% CI | Decile lift |
|---|---:|---:|---|---:|
| early_buyers | 2,170 | 0.359 | 0.336–0.384 | 0.02× |
| early_volume_sol | 2,179 | 0.553 | 0.527–0.581 | 3.33× |
| early_buy_volume_sol | 2,170 | 0.593 | 0.564–0.622 | 4.33× |
| concentration_top10 | 2,170 | 0.404 | 0.379–0.429 | 0.06× |
| creator_prior_launches | 2,179 | 0.593 | 0.563–0.622 | 3.15× |

## Secondary hypotheses (confirmation)

| Signal | n | AUC | 95% CI | Decile lift | Perm p | BH-adjusted p |
|---|---:|---:|---|---:|---:|---:|
| sniper_score | 2,170 | 0.356 | 0.335–0.378 | 0.00× | 1.000 | 1.000 |
| concentration_top10 | 2,170 | 0.404 | 0.379–0.429 | 0.06× | 1.000 | 1.000 |
| insider_score | 793 | 0.670 | 0.624–0.717 | 2.37× | 0.002 | 0.006 |

Secondary success bar: AUC ≥ 0.65 and CI lower bound > 0.55, considered after Holm-BH correction.

## Sensitivity checks (confirmation)

| Variant | n | AUC | 95% CI | Decile lift |
|---|---:|---:|---|---:|
| bundle_score → rug_1h | 2,057 | 0.449 | 0.441–0.457 | 0.24× |
| bundle_score → rug_6h | 2,127 | 0.451 | 0.442–0.459 | 0.29× |
| bundle_score → rug_12h | 2,170 | 0.452 | 0.444–0.461 | 0.28× |
| bundle_score → rug_24h | 2,175 | 0.452 | 0.443–0.460 | 0.28× |
| bundle_score → terminal rug 24h | 2,175 | 0.451 | 0.443–0.458 | 0.17× |
| 3-buyer bundle → rug 24h | 2,175 | 0.406 | 0.396–0.416 | 0.00× |

## Limitations

- No RPC funding graph in v0; bundle detection is same-slot co-buying.
- Concentration is trade-derived; transfers, burns and closed accounts are invisible.
- Post-migration AMM trades are not captured; migrated-token outcomes are stale.
- Creator history is constrained by the 72h capture; insider is exploratory.
- One venue and SOL-quoted coins only; USDC/other quote mints are excluded.
- Price-based rug definition only; no liquidity-pull data.
