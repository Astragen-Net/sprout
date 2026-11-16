# Phase 0 report — pumpfun launch signals

- Launches captured: **42,754**
- Eligible for 24h outcomes: **14,430**
- Exploration / confirmation: **10,101 / 4,329**
- 24h rug prevalence: **20.8%**
- Median early trades: **17**
- Median early buyers: **1**

## Primary hypothesis: bundle_score → 24h rug

**Amendment 1:** flagged = `bundle_score > 0`, unflagged = `bundle_score == 0`. The decile table is context only because ~94% of scores are zero.

| Period | n | Flagged n | Base rate | AUC | 95% CI | Flagged rug | Unflagged rug | Lift | Precision multiple |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Exploration | 6,830 | 476 | 22.1% | 0.456 | 0.453–0.460 | 0.6% | 23.7% | 0.03× | 0.03× |
| Confirmation | 2,875 | 183 | 18.3% | 0.462 | 0.456–0.468 | 0.5% | 19.5% | 0.03× | 0.03× |

**Pre-registered bar (Amendment 1):** AUC ≥ 0.7, CI lower bound > 0.6, flagged vs unflagged lift ≥ 1.5×, precision multiple ≥ 1.3× base rate, n ≥ 500, flagged n ≥ 200. **Result: FAIL**

### Confirmation deciles (context only)

| Decile | n | Mean bundle score | Observed rug rate |
|---:|---:|---:|---:|
| 1 | 288 | 0.000 | 17.4% |
| 2 | 287 | 0.000 | 20.2% |
| 3 | 288 | 0.000 | 19.8% |
| 4 | 287 | 0.000 | 12.9% |
| 5 | 288 | 0.000 | 14.9% |
| 6 | 287 | 0.000 | 27.9% |
| 7 | 287 | 0.000 | 22.0% |
| 8 | 288 | 0.000 | 20.5% |
| 9 | 287 | 0.000 | 20.6% |
| 10 | 288 | 0.428 | 7.3% |

## Baselines on confirmation

| Feature | n | AUC | 95% CI | Decile lift |
|---|---:|---:|---|---:|
| early_buyers | 2,875 | 0.378 | 0.359–0.399 | 0.01× |
| early_volume_sol | 2,889 | 0.516 | 0.493–0.538 | 1.08× |
| early_buy_volume_sol | 2,875 | 0.549 | 0.525–0.573 | 0.89× |
| concentration_top10 | 2,875 | 0.383 | 0.361–0.404 | 0.10× |
| creator_prior_launches | 2,889 | 0.571 | 0.548–0.594 | 2.18× |

## Secondary hypotheses (confirmation)

| Signal | n | AUC | 95% CI | Decile lift | Perm p | BH-adjusted p |
|---|---:|---:|---|---:|---:|---:|
| sniper_score | 2,875 | 0.368 | 0.349–0.387 | 0.02× | 1.000 | 1.000 |
| concentration_top10 | 2,875 | 0.383 | 0.361–0.404 | 0.10× | 1.000 | 1.000 |
| insider_score | 983 | 0.644 | 0.601–0.685 | 3.67× | 0.002 | 0.006 |

Secondary success bar: AUC ≥ 0.65 and CI lower bound > 0.55, considered after Holm-BH correction.

## Sensitivity checks (confirmation)

| Variant | n | AUC | 95% CI | Decile lift |
|---|---:|---:|---|---:|
| bundle_score → rug_1h | 2,813 | 0.462 | 0.455–0.467 | 0.46× |
| bundle_score → rug_6h | 2,835 | 0.462 | 0.456–0.467 | 0.43× |
| bundle_score → terminal rug 24h | 2,875 | 0.463 | 0.457–0.469 | 0.40× |
| 3-buyer bundle → rug 24h | 2,875 | 0.434 | 0.426–0.442 | 0.02× |

## Limitations

- No RPC funding graph in v0; bundle detection is same-slot co-buying.
- Concentration is trade-derived; transfers, burns and closed accounts are invisible.
- Post-migration AMM trades are not captured; migrated-token outcomes are stale.
- Creator history is constrained by the 72h capture; insider is exploratory.
- One venue and SOL-quoted coins only; USDC/other quote mints are excluded.
- Price-based rug definition only; no liquidity-pull data.
