# Phase 0 report — pumpfun launch signals (24h outcome)

**Data status:** the capture used for these results predates the first-buy decoder fix; see [`KNOWN_ISSUES.md`](../../KNOWN_ISSUES.md). Effect sizes are provisional.

- Launches captured: **122,121**
- Uncensored cohort (T+60s price, early trades): **54,629**
- Dead (no post-T+60s trade): **27,950**
- Observed 24h outcomes: **26,679**
- Exploration / confirmation: **18,675 / 8,004**
- 24h rug prevalence: **19.1%**
- Median early trades: **43**
- Median early buyers: **2**

## Primary hypothesis: bundle_score → 24h rug

**Amendment 1:** flagged = `bundle_score > 0`, unflagged = `bundle_score == 0`. The decile table is context only because ~94% of scores are zero.

| Period | n | Flagged n | Base rate | AUC | 95% CI | Flagged rug | Unflagged rug | Lift | Precision multiple |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Exploration | 18,437 | 1,864 | 18.7% | 0.441 | 0.438–0.444 | 1.0% | 20.6% | 0.05× | 0.05× |
| Confirmation | 7,896 | 681 | 20.7% | 0.450 | 0.446–0.455 | 1.9% | 22.5% | 0.08× | 0.09× |

**Pre-registered bar (Amendment 1):** AUC ≥ 0.7, CI lower bound > 0.6, flagged vs unflagged lift ≥ 1.5×, precision multiple ≥ 1.3× base rate, n ≥ 500, flagged n ≥ 200. **Result: FAIL**

### Confirmation deciles (context only)

| Decile | n | Mean bundle score | Observed rug rate |
|---:|---:|---:|---:|
| 1 | 790 | 0.000 | 27.0% |
| 2 | 790 | 0.000 | 21.4% |
| 3 | 789 | 0.000 | 17.2% |
| 4 | 790 | 0.000 | 22.5% |
| 5 | 789 | 0.000 | 22.4% |
| 6 | 790 | 0.000 | 22.7% |
| 7 | 789 | 0.000 | 22.8% |
| 8 | 790 | 0.000 | 22.7% |
| 9 | 789 | 0.000 | 24.0% |
| 10 | 790 | 0.498 | 4.8% |

## Baselines on confirmation

| Feature | n | AUC | 95% CI | Decile lift |
|---|---:|---:|---|---:|
| early_buyers | 7,896 | 0.374 | 0.361–0.387 | 0.03× |
| early_volume_sol | 8,004 | 0.537 | 0.523–0.552 | 0.83× |
| early_buy_volume_sol | 7,896 | 0.566 | 0.552–0.580 | 1.37× |
| concentration_top10 | 7,896 | 0.437 | 0.423–0.450 | 0.09× |
| creator_prior_launches | 8,004 | 0.593 | 0.578–0.608 | 2.68× |

## Secondary hypotheses (confirmation)

| Signal | n | AUC | 95% CI | Decile lift | Perm p | BH-adjusted p |
|---|---:|---:|---|---:|---:|---:|
| sniper_score | 7,896 | 0.358 | 0.347–0.370 | 0.02× | 1.000 | 1.000 |
| concentration_top10 | 7,896 | 0.437 | 0.423–0.450 | 0.09× | 1.000 | 1.000 |
| insider_score | 1,977 | 0.651 | 0.626–0.677 | 4.50× | 0.002 | 0.006 |

Secondary success bar: AUC ≥ 0.65 and CI lower bound > 0.55, considered after Holm-BH correction.

## Sensitivity checks (confirmation)

| Variant | n | AUC | 95% CI | Decile lift |
|---|---:|---:|---|---:|
| bundle_score → rug_1h | 7,542 | 0.448 | 0.444–0.453 | 0.15× |
| bundle_score → rug_6h | 7,771 | 0.450 | 0.445–0.454 | 0.17× |
| bundle_score → rug_12h | 7,859 | 0.450 | 0.446–0.454 | 0.18× |
| bundle_score → rug_24h | 7,896 | 0.450 | 0.446–0.455 | 0.18× |
| bundle_score → terminal rug 24h | 7,896 | 0.451 | 0.447–0.455 | 0.18× |
| 3-buyer bundle → rug 24h | 7,896 | 0.416 | 0.410–0.421 | 0.02× |

## Limitations

- No RPC funding graph in v0; bundle detection is same-slot co-buying.
- Concentration is trade-derived; transfers, burns and closed accounts are invisible.
- Post-migration AMM trades are not captured; migrated-token outcomes are stale.
- Creator history is constrained by the 72h capture; insider is exploratory.
- One venue and SOL-quoted coins only; USDC/other quote mints are excluded.
- Price-based rug definition only; no liquidity-pull data.
- Dead launches (no post-T+60s trade) are reported separately and excluded from the price-based rug AUC.
- Captures made before the first-buy fix may misstate early buy amounts; see `KNOWN_ISSUES.md`.
