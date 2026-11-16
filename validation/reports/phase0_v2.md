# Phase 0 v2 — insider-network validation

- Fresh window start: `2026-11-15T00:00:00Z`
- Fresh launches with 24h outcomes: **23,709**
- Known-creator launches: **5,624**
- 24h rug prevalence among fresh eligible: **20.5%**

## Primary: insider_score → 24h rug

| n known | AUC | 95% CI | High cohort (≥0.9) n | High rug | Rest rug | Lift | Precision multiple |
|---:|---:|---|---:|---:|---:|---:|---:|
| 3,025 | 0.649 | 0.628–0.671 | 2,151 | 24.4% | 7.1% | 3.44× | 1.26× |

**Pre-registered bar:** AUC ≥ 0.65, CI lower > 0.55, high-cohort lift ≥ 1.5×, precision ≥ 1.3× base rate, n ≥ 200. **Result: FAIL**

## Secondary signals

| Signal | n | AUC | 95% CI | Perm p | BH-adjusted p |
|---|---:|---:|---|---:|---:|
| insider_score_expanded | 9,795 | 0.607 | 0.596–0.616 | 0.002 | 0.003 |
| insider_score_2plus | 9,795 | 0.618 | 0.607–0.629 | 0.002 | 0.003 |
| creator_prior_launches | 11,988 | 0.601 | 0.590–0.611 | 0.002 | 0.003 |
| bundle_score (negative control) | 11,823 | 0.448 | 0.445–0.452 | 1.000 | 1.000 |

## Combined model (fit on v1, evaluated on fresh)

- Features: creator_prior_launches, insider_score, early_buy_volume_sol
- Train n: 3,757; test n: 3,025
- AUC: **0.628**

## Limitations

- Pumpfun and SOL-quoted coins only; price-based rug definition.
- No funding-graph tracing; insider is a repeat-buyer proxy.
- Coverage depends on prior launches; the 24h window limits the fresh sample.
- Do not tune thresholds on this window; a secondary pass without the primary is not confirmation.
